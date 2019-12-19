import warnings

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.apps import apps
from django.core import exceptions
from django.utils.timezone import make_aware

from polymorphic.models import PolymorphicModel

#import django.contrib.gis.db.models as gismodels # For very advanced GIS features
from django.contrib.postgres.fields import ArrayField, JSONField

from django_pandas.managers import DataFrameQuerySet

#from .result import Result
from .user import UserProfile
from .object import Object
from ..postgres import ArrayPosition, ArrayPositions, Unnest

import arrow
import pint
import geopy
import datetime
import version_parser.version as version
import re
from scipy.sparse import coo_matrix

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
            value = VersionParser(value, parse_number=True)
        except ValueError:
            raise exceptions.ValidationError(self.error_messages['invalid'] % value)
        return value

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return VersionParser(value, parse_number=True)

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
    description = models.TextField(blank=True) #This seems useful to have... can store the interpretation for data with this signature
    value_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    data_types = models.ManyToManyField(ContentType, related_name="+")
    values = models.ManyToManyField("Value", related_name="signature")

    #Flags for certain DataSignature types
    #Feature Annotation: This Value provides a human-readable label for a feature
    feature_annotation = models.BooleanField(default=False)

    # 0: None of these linked to these values
    # Positive integer: This many, exactly, are linked to these values
    # -1: Any number of these objects may be attached (including 0) NOTE: Currently unused case?
    # -2: Any positive number of these objects may be attached
    object_counts = JSONField()

    def __str__(self):
        link_str = ", ".join(["%d %s" % (self.object_counts[Obj.plural_name],Obj.plural_name) for Obj in Object.get_object_types()])
        return "%s '%s' storing %s, linked to %s" % (str(self.value_type).capitalize(), self.name, ", ".join([x.model_class().__name__ for x in self.data_types.all()]), link_str)

    @classmethod
    def create(cls, name, value_type, object_counts):
        for Obj in Object.get_object_types():
            if Obj.plural_name not in object_counts:
                object_counts[Obj.plural_name] = 0
        signature = DataSignature(name=name, 
                                  value_type=ContentType.objects.get_for_model(value_type), 
                                  object_counts=object_counts)
        signature.save()
        return signature

    @classmethod
    def get_or_create(cls, name, **kwargs):
        signatures, object_counts = cls.get(name, return_counts=True, **kwargs)
        if not signatures.exists():
            signature = cls.create(name, kwargs['value_type'], object_counts)
            signatures = DataSignature.objects.filter(pk=signature.pk)
        return signatures

    @classmethod
    def get(cls, name, value_type, return_counts=False, **kwargs):
        object_counts = {}
        object_querysets = {}
        for Obj in Object.get_object_types():
            if Obj.plural_name in kwargs:
                if type(kwargs[Obj.plural_name]) in [models.query.QuerySet, DataFrameQuerySet]:
                    object_counts[Obj.plural_name] = kwargs[Obj.plural_name].count()
                    object_querysets[Obj.plural_name] = kwargs[Obj.plural_name]
                elif type(kwargs[Obj.plural_name]) == int:
                    object_counts[Obj.plural_name] = kwargs[Obj.plural_name]
                elif type(kwargs[Obj.plural_name]) == bool:
                    object_counts[Obj.plural_name] = int(kwargs[Obj.plural_name])
            else:
                object_counts[Obj.plural_name] = 0
        if type(value_type) == ContentType:
            ctype = value_type
        elif type(value_type) == str:
            ctype = ContentType.objects.get_for_model(Value.get_value_types(type_name=value_type))
        else:
            ctype = ContentType.objects.get_for_model(value_type)
        signatures = DataSignature.objects.filter(name=name,
                     object_counts=object_counts,
                     value_type=ctype)
        if return_counts:
            return (signatures, object_counts)
        return signatures

#Generic superclass that allows us to automatically list
#Any new types defined here without needing to know their
#names out there
class Data(PolymorphicModel):
    type_name = "data"
    atomic = False
    native_type = None
    cast_function = lambda x: x
    db_cast_function = lambda x: x

    values = models.ManyToManyField("Value", related_name="data")

    @classmethod
    def get_data_types(cls, data=None, type_name=None, **kwargs):
        #Convenience function for get_data_types that returns one by name, or
        #returns the inferred value, if not named
        # Take in a string data_type and return the Datum model
        if type_name is not None:
            for datum in Data.get_data_types():
                if (datum.type_name == type_name.lower()) or (datum.__name__.lower() == type_name.lower()):
                    return datum
            raise ValueError("Unrecognized requested 'data_type'/'type_name' of %s" % (type_name,))
        if data is not None:
            return cls.infer_type(data, **kwargs)
        data_subclasses = set()
        def all_subclasses(c, data_subclasses):
            for sc in c.__subclasses__():
                data_subclasses.add(sc)
                data_subclasses = all_subclasses(sc, data_subclasses)
            return data_subclasses
        return all_subclasses(Data, data_subclasses)

    def __str__(self):
        return str(self.get_value())

    def __unicode__(self):
        return str(self.get_value())

    @classmethod
    def cast(cls, value):
        # Casts for writing to the Postgres DB
        # so the return value must be something Django can cast from
        #NOTE: This must be overridden any time the cast_function isn't sufficient
        # for converting a value to something acceptable for the database
        if (type(value) != str) and (type(value) == cls.native_type):
            return cls.db_cast_function(value)
        else:
            return cls.db_cast_function(cls.cast_function(value))

    #Most of the time, this is very simple
    #But some data types have to store the data in multiple parts
    #and get_data will reconstitute it in Python form
    def get_value(self):
        return self.value

    @classmethod
    def infer_type(cls, value, **kwargs):
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
            if (type(value) != str) and (type(value) == vtype.native_type):
                # Catch and handle it more specifically if it's a Pint unit
                if type(value) == Q_:
                    for qtype in PintDatum.get_data_types():
                        if qtype.eq_dimensionality(value):
                            return qtype
                return vtype
        # Finally, we go through the types in a sensible order, trying casts
        # until one works
        cast_order = [ IntDatum, FloatDatum, DatetimeDatum, CoordDatum ] + \
                     [ VersionDatum ] + PintDatum.__subclasses__()
        castable = []
        for mdl in cast_order:
            try:
                #NOTE: Not mdl.cast() because this 
                mdl.cast_function(value)
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
            value = cls.cast(value)
        except:
            raise ValueError("Cannot parse value %s with cast function for data type %s" % (str(value), cls.type_name))
        if type(value) != dict:
            qs = cls.objects.filter(value=value)
            if qs.exists():
                return qs.get()
            obj = cls.objects.create(value=value)
        else:
            #Special case: only MatrixDatum at the moment
            #qs = cls.objects.filter(**value)
            #if qs.exists():
            #    return qs.get()
            obj = cls.objects.create(**value)
        return obj

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
    cast_function = lambda x: make_aware(arrow.get(x, "DD/MM/YYYY").datetime)
    db_cast_function: lambda x: make_aware(x)
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
for Obj in Object.get_object_types():
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

    def __str__(self):
        return str(self.value * self.default_unit)
    
    @classmethod
    def db_cast_function(cls, x):
        return x.to(cls.default_unit).magnitude

    @classmethod
    def cast_function(cls, x):
        val = unitregistry(x).to(cls.default_unit)
        if type(val) == cls.native_type:
            return val
        else:
            raise ValueError

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

    @classmethod
    def cast_function(cls, x):
        if "and" in x:
            val = sum([unitregistry(t.replace("and","")).to(cls.default_unit) for t in x.split(",") if "microseconds" not in t])
        else:
            val = unitregistry(x).to(cls.default_unit)
        if type(val) == cls.native_type:
            return val
        else:
            raise ValueError

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

# If we ever want use GeoDjango, this will have to be converted to gismodels.PointField()
class CoordDatum(Data):
    type_name = "coordinate"
    native_type = geopy.point.Point
    cast_function = geopy.point.Point
    db_cast_function = lambda x: [x.latitude, x.longitude, x.altitude]
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
    db_cast_function = lambda x: x.address
    value = models.TextField()

class ImageDatum(Data):
    type_name = "image"
    cast_function = None #TODO
    value = models.ImageField() # TODO

class BibtexDatum(Data):
    type_name = "bibtex"
    value = models.TextField()

class LinkDatum(Data):
    type_name = "link"
    value = models.TextField()

class LocalLinkDatum(LinkDatum):
    #Links received with a reverse() via Django
    type_name = "locallink"

class ExternalLinkDatum(LinkDatum):
    #Links that go outside of the Django app
    type_name = "externallink"

class UploadFileDatum(Data):
    #Local server file paths
    type_name = "uploadfile"
    value = models.ForeignKey("UploadFile", on_delete=models.CASCADE)

class UserDatum(Data):
    type_name = "user"
    cast_function = lambda x: UserProfile.objects.get(pk=x)
    value = models.ForeignKey("UserProfile", on_delete=models.CASCADE)

class MatrixDatum(Data):
    # A container for Sparse Matrices
    type_name = "coomatrix"
    native_type = coo_matrix
    db_cast_function = lambda x: {'value': x.data.tolist(), 'row': x.row.tolist(), 'col': x.col.tolist(), 
                                  'rowobj': ContentType.objects.get_by_natural_key('db', x.rowobj),
                                  'colobj': ContentType.objects.get_by_natural_key('db', x.colobj)}
    value = ArrayField(base_field=models.FloatField())
    row = ArrayField(base_field=models.IntegerField())
    col = ArrayField(base_field=models.IntegerField())
    # Generally intended to be Object subclasses, but I could see abusing this for other purposes
    rowobj = models.ForeignKey(ContentType, related_name="matrix_row", on_delete=models.CASCADE)
    colobj = models.ForeignKey(ContentType, related_name="matrix_col", on_delete=models.CASCADE)
    def __str__(self):
        return "COO Matrix with %d non-zero values" % (len(self.value),)
    def get_value(self):
        return coo_matrix((self.value, (self.row, self.col)))
    def register_observations(self):
        assert colobj == ContentType.objects.get_by_natural_key('db.Sample')
        # Grab all unique pks in col
        samples = MatrixDatum.objects.filter(pk=self.pk).annotate(samples=Unnest('col', distinct=True)).values_list("samples",flat=True)
        for sample_pk in samples:
            # Grab the positions in the matrix where it's the column value for this pk
            pos = MatrixDatum.objects.filter(pk=self.pk).annotate(pos=ArrayPositions("col",sample_pk)).get().pos
            # Grab the feature pks by grabbing those indices
            feats = MatrixDatum.objects.filter(pk=self.pk).values_list(*["row__%d" % (p,) for p in pos]).get()
            # Add the features to the Sample
            Sample.objects.get(pk=sample_pk).features.add(*Feature.objects.filter(pk__in=feats))

#class BitStringDatum(Data):
#    type_name = "bitstring"
#    cast_function = None
#    values = BitStringField() #TODO: borrow from django_postgres

class SequenceDatum(Data):
    # A container for a biological sequence
    type_name = "sequence"
    value = models.TextField()

