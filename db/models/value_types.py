from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.conf import settings

import django.contrib.gis.db.models as gismodels

from .result import Result

import arrow
import pint
import geopy

unitregistry = pint.UnitRegistry()
pint.set_application_registry(unitregistry)

#Generic superclass that allows us to automatically list
#Any new types defined here without needing to know their
#names out there
class ValueDataType(models.Model):
    val_obj = GenericRelation("Value")
    class Meta:
        abstract = True

    @classmethod
    def get_datatypes(cls):
        return cls.__subclasses__()

class StrDatum(ValueDataType):
    type_name = "str"
    cast_function = str
    value = models.TextField()

class IntDatum(ValueDataType):
    type_name = "int"
    cast_function = int
    value = models.IntegerField()

class FloatDatum(ValueDataType):
    type_name =  "float"
    cast_function = float
    value = models.FloatField()

class DatetimeDatum(ValueDataType):
    type_name = "datetime"
    cast_function = arrow.get
    value = models.DateTimeField()

#This is if the input parameter is another result, ie. another artifact searched by UUID
class ResultDatum(ValueDataType):
    type_name = "result"
    cast_function = lambda x: Result.objects.get(uuid=str(x))
    value = models.ForeignKey("Result", on_delete=models.CASCADE)
    def __str__(self):
        return value.name

# Using definitions from Pint to power these
# and allow arbitrary units and standardized representation

# TODO: cast function wrappers for unitregistry that attempt to keep 
#       users in a lane convertible from the default unit
#       and some way to change the units stored on disk with a warning
#       that conversions are destructive

class VolumeDatum(ValueDataType):
    type_name = "volume"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "litre")

class ConcentrationDatum(ValueDataType):
    type_name = "concentration"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "molar")

class MassDatum(ValueDataType):
    type_name = "mass"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "gram")

class TemperatureDatum(ValueDataType):
    type_name = "temperature"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "celsius")

# This is NOT a Datetime, but rather an *amount* of time
class TimeDatum(ValueDataType):
    type_name = "time"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "second")

class LengthDatum(ValueDataType):
    type_name = "length"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "metre")

class FrequencyDatum(ValueDataType):
    type_name = "frequency"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "hertz")

class VelocityDatum(ValueDataType):
    type_name = "velocity"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "metre / second")

class EnergyDatum(ValueDataType):
    type_name = "energy"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "calorie")

class PressureDatum(ValueDataType):
    type_name = "pressure"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "pascal")

class ViscosityDatum(ValueDataType):
    type_name = "viscosity"
    cast_function = unitregistry
    value = models.FloatField()
    stored_unit = models.CharField(max_length=256, default = "poise")

def geopy_to_django(point_str):
    point = geopy.point.Point(point_str)
    #Simply discard the elevation
    return (point.latitude, point.longitude)

# Using geopy.point.Point
class CoordDatum(ValueDataType):
    type_name = "coordinate"
    cast_function = geopy_to_django
    value = gismodels.PointField()
    
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
class AreaDatum(ValueDataType):
    type_name = "area"
    cast_function = polygon_parser
    value = gismodels.PolygonField()
