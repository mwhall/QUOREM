import warnings

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.apps import apps
from django.core import exceptions

from polymorphic.models import PolymorphicModel

#import django.contrib.gis.db.models as gismodels # For very advanced GIS features
from django.contrib.postgres.fields import ArrayField

#from .result import Result
from .user import UserProfile
from .object import Object

import arrow
warnings.simplefilter("ignore", arrow.factory.ArrowParseWarning)
import pint
import geopy
import datetime
import version_parser.version as version
import re
from scipy.sparse import csr_matrix

object_classes = Object.get_object_classes()

#This should be fine to live here, but may need to move if this file reloads often
unitregistry = pint.UnitRegistry()
pint.set_application_registry(unitregistry)
Q_ = unitregistry.Quantity
# CUSTOM FIELDS AND PARSERS
# Probably move these to a fields.py soon

class VersionParser(version.Version):
    digits = 4
    number_version_pattern = re.compile(r"^(\d{1,%d})$" % (digits*3,))
    def __init__(self, raw_version, parse_number=False, *args, **kwargs):
        if not parse_number:
            self.number_version_pattern = re.compile(r"$a") #thanks StackOverflow, for this regex that's guaranteed not to match
        super().__init__(raw_version, *args, **kwargs)

    def __str__(self):
        return self.get_typed_version(version.VersionType.VERSION)

    def __repr__(self):
        return self.__str__()

    def get_number(self):
        filled_major = str(self._major_version).rjust(self.digits, "0")
        filled_minor = str(self._minor_version).rjust(self.digits, "0")
        filled_build = str(self._build_version).rjust(self.digits, "0")
        return int("{}{}{}".format(filled_major, filled_minor, filled_build))

    def _parse(self, any_version):
        str_version = str(any_version)
        result_dict = {}
        if self.number_version_pattern.match(str_version):
            result = self.number_version_pattern.match(str_version)
            result_dict["type"] = version.VersionType.NUMBER
            reversed_nr = self._reverse(result.group(1))
            version_pieces = [reversed_nr[i:i + self.digits] for i in range(0, len(reversed_nr), self.digits)]
            result_dict["build"] = int(self._reverse(version_pieces[0]))
            if len(version_pieces) > 1:
                result_dict["minor"] = int(self._reverse(version_pieces[1]))
            else:
                result_dict["minor"] = 0
            if len(version_pieces) > 2:
                result_dict["major"] = int(self._reverse(version_pieces[2]))
            else:
                result_dict["major"] = 0
            return result_dict
        else:
            return super()._parse(any_version)

def validate_version(version):
    try:
        VersionParser(str(version))
    except ValueError:
        raise exceptions.ValidationError("%s is not a valid version string" % (version_str,))

### Custom Field so that we can use Django's greater than and less than filters on Versions
class VersionField(models.BigIntegerField):
    default_error_messages = {
            'invalid': "'%s' value must be a version string "
                       "(in this form: X.Y.Z).",
        }
    default_validators = [validate_version]
    
    def to_python(self, value):
        if value is None:
            return None
        try:
            value = VersionParser(str(value))
        except ValueError:
            raise exceptions.ValidationError(self.error_messages['invalid'] % value)
        return value

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return VersionParser(str(value))

    def get_prep_value(self, value):
        return self.to_python(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        if not prepared:
            value = self.get_prep_value(value)
        if value is None:
            return value
        return value.get_number()

class DataSignature(models.Model):
    name = models.CharField(max_length=512)
    description = models.TextField() #This seems useful to have... can store the interpretation for data with this signature
    value_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    data_types = models.ManyToManyField(ContentType)
    # 0: None of these linked to these values
    # Positive integer: This many, exactly, are linked to these values
    # -1: Any number of these objects may be attached (including 0) NOTE: Currently unused case?
    # -2: Any positive number of these objects may be attached
    object_counts = ArrayField(base_field=models.IntegerField(default=0),
                               size=len(object_classes))
    # Just to make sure we keep this association concrete since
    # the order of object_classes might change on reboot, 
    # but definitely with Object additions
    current_models = [ ContentType.objects.get_for_model(Obj) for Obj in object_classes ]
    assert len(current_models) > 0 # Overly cautious, but default can't be [] according to Django
    object_models = ArrayField(base_field=models.ForeignKey(ContentType, on_delete=models.CASCADE), size=len(object_classes), default=current_models)
    # NOTE: How would migrating this work? I assume it'd expand the size of the 
    # arrays, and then we'd have to add the new Object to each of the object_models in each of the signatures

    def __str__(self):
        link_str = ", ".join([str(self.object_counts[idx]) + " " + Obj.plural_name for idx, Obj in enumerate(object_classes)])
        return "Data Signature: %s %s storing %s, linked to %s" % (self.value_type.__name__, self.name, self.data_type.__name__, link_str)

    @classmethod
    def get(cls, name, value_type=None, **kwargs):
        if value_type is not None:
            if type(value_type) == str:
                value_type = Data.get_data_type(
                
        # Return the matching DataSignature
        signatures = cls.objects.filter(name=name, 

#Generic superclass that allows us to automatically list
#Any new types defined here without needing to know their
#names out there
class Data(PolymorphicModel):
    #Does this stay in RAM?
    type_cache = {}
    type_name = "data"
    atomic = False
    native_type = None
    cast_function = lambda x: x

    @classmethod
    def get_data_types(cls):
        return cls.__subclasses__()

    @classmethod
    def get_data_type(cls, data_type):
        # Take in a string data_type and return the Datum model
        for datum in Data.get_data_types():
            if (datum.type_name == data_type.lower()) or (datum.__name__ == data_type):


    @classmethod
    def infer_type(cls, data, **kwargs):
        #First, check if the user piped us a hint/request
        if "data_type" in kwargs:
            requested_type = kwargs["data_type"]
            for vtype in cls.get_data_types():
                if requested_type == vtype.type_name:
                    return vtype
            #Couldn't find the hint, warn and infer
            warnings.warn("Could not find requested data type %s, attempting to infer" % (kwargs["data_type"],))
        #Second, check if the data is of an advanced type that we understand
        for vtype in cls.get_data_types():
            if (type(data) != str) and (type(data) == vtype.native_type):
                # Catch and handle it more specifically if it's a Pint unit
                if type(data) == Q_:
                    for qtype in PintDatum.get_data_types():
                        if qtype.eq_dimensionality(data):
                            return qtype
                return vtype
        # Finally, we go through the types in a sensible order, trying casts
        # until one works
        cast_order = [ IntDatum, FloatDatum, DatetimeDatum, CoordDatum ] + \
                       PintDatum.get_data_types() + [ VersionDatum ]
        castable = []
        for mdl in cast_order:
            try:
                mdl.cast_function(data)
                castable.append(mdl)
            except:
                pass
        if len(castable) == 0:
            return StrDatum
        elif len(castable) == 1:
            return castable[0]
        else:
            warnings.warn("Data can be coerced into multiple types (%s). Choosing the first one, %s" % (", ".join([x.__name__ for x in castable]), castable[0].__name__))
            return castable[0]

    @classmethod
    def get_or_create(cls, value, **kwargs):
        try:
            value = cls.cast_function(str(value))
        except:
            raise ValueError("Cannot parse value %s with cast function for data type %s" % (str(value), cls.type_name))
        qs = cls.objects.filter(value=value)
        if qs.exists():
            return qs.get()
        obj = cls.objects.create(value=value)
        return obj

    #Most of the time, this is very simple
    #But some data types have to store the data in multiple parts
    #and get_data will reconstitute it in Python form
    def get_value(self):
        return self.value

class StrDatum(Data):
    atomic = True
    type_name = "str"
    native_type = str
    cast_function = str
    value = models.TextField()

class IntDatum(Data):
    atomic = True
    type_name = "int"
    native_type = str
    cast_function = int
    value = models.IntegerField()

class FloatDatum(Data):
    atomic = True
    type_name =  "float"
    native_type = float
    cast_function = float
    value = models.FloatField()

class DatetimeDatum(Data):
#    default_date_format = "DD/MM/YYYY" #TODO: This needs a better home. Global defaults somewhere?
    type_name = "datetime"
    native_type = datetime.datetime
    cast_function = lambda x: arrow.get(x, "DD/MM/YYYY").datetime
    value = models.DateTimeField()

class VersionDatum(Data):
    type_name = "version"
    native_type = version.Version
    cast_function = lambda x: VersionParser(x, parse_number=False)
    value = VersionField()

    def __str__(self):
        if type(self.value) == VersionParser:
            return self.value.get_typed_version(version.VersionType.VERSION)
        else:
            return self.value
    def __repr__(self):
        return self.__str__()

def datum_factory(obj):
    object_class_name = obj.base_name.capitalize() + "Datum"
    class Meta:
        app_label = "db"
    cls = type(object_class_name, (Data,), 
              {'type_name': obj.base_name,
               'value': models.ForeignKey(obj.base_name.capitalize(), on_delete=models.CASCADE),
               '__module__': 'db.models.data_types',
               'Meta': Meta,
               'native_type': obj})
    cls.cast_function = lambda x: obj.objects.get(**{obj.id_field: str(x)})
    cls.__str__ = lambda x: str(x.value)
    return cls

#NOTE: These aren't directly importable from here... any way to get these into
# the file's namespace?
for Obj in Object.get_object_classes():
    datum_factory(Obj)

# Using definitions from Pint to power these
# and allow arbitrary units and standardized representation

# TODO: cast function wrappers for unitregistry that attempt to keep 
#       users in a lane convertible from the default unit
#       and some way to change the units stored on disk with a warning
#       that conversions are destructive

class PintDatum(Data):
    type_name = "pint"
    default_unit = unitregistry.Unit("dimensionless")
    native_type = Q_
    value = models.FloatField()
    
    @classmethod
    def cast_function(cls, x):
        return unitregistry(x).to(cls.default_unit)

    @classmethod
    def eq_dimensionality(cls, quantity):
        return cls.default_unit.dimensionality == quantity.dimensionality

class VolumeDatum(PintDatum):
    type_name = "volume"
    default_unit = unitregistry.Unit("litre")

class ConcentrationDatum(PintDatum):
    type_name = "concentration"
    default_unit = unitregistry.Unit("molar")

class MassDatum(PintDatum):
    type_name = "mass"
    default_unit = unitregistry.Unit("gram")

class TemperatureDatum(PintDatum):
    type_name = "temperature"
    default_unit = unitregistry.Unit("celsius")

    @classmethod
    def cast_function(cls, x):
        unitregistry.autoconvert_offset_to_baseunit = True
        quantity = unitregistry(x).to(cls.default_unit)
        unitregistry.autoconvert_offset_to_baseunit = False
        return quantity


# This is NOT a Datetime, but rather an *amount* of time
class TimeDatum(PintDatum):
    type_name = "time"
    default_unit = unitregistry.Unit("second")

class LengthDatum(PintDatum):
    type_name = "length"
    default_unit = unitregistry.Unit("metre")

class FrequencyDatum(PintDatum):
    type_name = "frequency"
    default_unit = unitregistry.Unit("hertz")

class VelocityDatum(PintDatum):
    type_name = "velocity"
    default_unit = unitregistry.Unit("metre / second")

class EnergyDatum(PintDatum):
    type_name = "energy"
    default_unit = unitregistry.Unit("calorie")

class PressureDatum(PintDatum):
    type_name = "pressure"
    default_unit = unitregistry.Unit("pascal")

class ViscosityDatum(PintDatum):
    type_name = "viscosity"
    default_unit = unitregistry.Unit("poise")

def geopy_to_django(point_str):
    point = geopy.point.Point(point_str)
    #Simply discard the elevation
    return [point.latitude, point.longitude, point.altitude]

# If we ever want use GeoDjango, this will have to be converted to gismodels.PointField()
class CoordDatum(Data):
    type_name = "coordinate"
    native_type = geopy.point.Point
    cast_function = geopy_to_django
    value = ArrayField(base_field=models.FloatField(), size=3)
    
def polygon_parser(poly_str):
    point_strings = poly_str.split(";")
    points = []
    for point_str in point_strings:
        point = geopy_to_django(point_str)
        point = (point.latitude, point.longitude)
        points.append(point)
    assert points[0] == points[-1], "First and last point must match to define a closed polygon for AreaDatum"
    return points

# GEOS-style Polygon, but we only parse one LinearRing here with above function
#class AreaDatum(Data):
#    type_name = "area"
#    cast_function = polygon_parser
#    value = gismodels.PolygonField()

# These can be parsed from geoencoders from geopy for standardization
class LocationDatum(Data):
    type_name = "textlocation"
    cast_function = geopy.location.Location
    native_type = geopy.location.Location
    value = models.TextField()

class ImageDatum(Data):
    type_name = "image"
    cast_function = None #TODO
    value = models.ImageField() # TODO

class BibtexDatum(Data):
    type_name = "bibtex"
    cast_function = None #TODO
    value = models.TextField()

class LinkDatum(Data):
    type_name = "link"
    cast_function = None #TODO
    value = models.TextField()

class LocalLinkDatum(LinkDatum):
    #Links received with a reverse() via Django
    type_name = "locallink"

class ExternalLinkDatum(LinkDatum):
    #Links that go outside of the Django app
    type_name = "externallink"

class FileDatum(Data):
    #Local server file paths
    type_name = "file"
    cast_function = None #TODO
    value = models.ForeignKey("File", on_delete=models.CASCADE)

class UserDatum(Data):
    type_name = "user"
    cast_function = lambda x: UserProfile.objects.get(pk=x)
    value = models.ForeignKey("UserProfile", on_delete=models.CASCADE)

class MatrixDatum(Data):
    # A container for Sparse Matrices
    type_name = "matrix"
    native_type = csr_matrix
    cast_function = None # We can't cast this from a String
    value = ArrayField(base_field=models.FloatField())
    indptr = ArrayField(base_field=models.IntegerField())
    index = ArrayField(base_field=models.IntegerField())
    def get_data(self):
        pass

#class BitStringDatum(Data):
#    type_name = "bitstring"
#    cast_function = None
#    values = BitStringField() #TODO: borrow from django_postgres

class SequenceDatum(Data):
    # A container for a biological sequence
    type_name = "sequence"
    cast_function = None #TODO
    value = models.TextField()

