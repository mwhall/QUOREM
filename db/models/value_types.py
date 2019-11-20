from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.conf import settings

from .result import Result

import arrow

class ValType(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def get_value_classes(cls):
        return cls.__subclasses__()

class StrVal(ValType):
    type_name = "str"
    cast_function = str
    value = models.TextField()
    val_obj = GenericRelation("Value",related_query_name=type_name)

class IntVal(ValType):
    type_name = "int"
    cast_function = int
    value = models.IntegerField()
    val_obj = GenericRelation("Value", related_query_name=type_name)

class FloatVal(ValType):
    type_name =  "float"
    cast_function = float
    value = models.FloatField()
    val_obj = GenericRelation("Value", related_query_name=type_name)

class DatetimeVal(ValType):
    type_name = "datetime"
    cast_function = arrow.get
    value = models.DateTimeField()
    val_obj = GenericRelation("Value", related_query_name=type_name)

#This is if the input parameter is another result, ie. another artifact searched by UUID
class ResultVal(ValType):
    type_name = "result"
    cast_function = lambda x: Result.objects.get(uuid=str(x))
    value = models.ForeignKey('Result', on_delete=models.CASCADE)
    val_obj = GenericRelation("Value", related_query_name=type_name)

    def __str__(self):
        return value.name + ": " + value.type

