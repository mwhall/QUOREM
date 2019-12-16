#object manager experiment
from polymorphic.models import PolymorphicModel
from polymorphic.managers import PolymorphicManager
from polymorphic.query import PolymorphicQuerySet
from django.db import models
from db.models.object import Object

#This is the novel part
class ValuDatuh(PolymorphicQuerySet):
    def add_datuh_value(self):
        datuh_query = (
            Datuh
            .objects
            .filter(id__in=[models.OuterRef('datuh')])
            .values('value')
        )
        return self.annotate(
            datuh=Subquery(
                datuh_query
                )
            )

class Valu(PolymorphicModel):
    base_name='valu'
    plural_name='valus'

    name = models.CharField(max_length=512)
    datuh = models.ForeignKey('Datuh', related_query_name="valus", on_delete=models.CASCADE)

    #Custom manager!
    my_objects = PolymorphicManager.from_queryset(ValuDatuh)

class OneValuType(Valu):
    base_name="this_valu"
    plural_name = "these_valus"

class AnotherValuType(Valu):
    base_name="that_valu"
    plural_name="those_values"


class Datuh(PolymorphicModel):
    type_name = "datuh"
    atomic = False
    native_type = None

class StringDatuhm(Datuh):
    atomic= True
    type_name= "str"
    native_type = str
    value = models.TextField()

class IntDatuhm(Datuh):
    atomic = True
    type_name = 'int'
    native_type = int
    value = models.IntegerField()

class Resolt(Object):
    base_name = 'resolt'
    plural_name = 'resolts'
    has_upstream = True
    name = models.CharField(max_length=255, unique=True)
    valus = models.ManyToManyField('Valu', related_name = 'resolts', blank=True)
