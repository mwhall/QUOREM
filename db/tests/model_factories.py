import factory
import random
from factory.django import DjangoModelFactory
from django.contrib.contenttypes.models import ContentType
from db.models import *

"""############################################################################
###      Factories for base objects                                         ###
############################################################################"""
#by default creates a process with 4 metadata values
class ProcessFactory(DjangoModelFactory):
    @factory.sequence
    def name(n):
        return "test_process_%d" % n
    description = factory.Faker('sentence', nb_words=8)

    @factory.post_generation
    def values(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for value in extracted:
                self.values.add(value)
        else:
            for i in range(4):
                self.values.add(LinkedStrValFactory(type='metadata'))

    class Meta:
        model = Process

#By default creates a Step with one linked process and one parameter
class StepFactory(DjangoModelFactory):
    @factory.sequence
    def name(n):
        return "test_step_%d" % n
    description = factory.Faker('sentence', nb_words=8)

    @factory.post_generation
    def processes(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for process in extracted:
                self.processes.add(value)
        else:
            self.processes.add(ProcessFactory())

    @factory.post_generation
    def values(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for value in extracted:
                self.values.add(value)
        else:
            self.values.add(LinkedFloatValFactory(type='parameter'))
    class Meta:
        model = Step

#Default is to make an Investigation with 2 linked metadata values
class InvestigationFactory(DjangoModelFactory):
    @factory.sequence
    def name(n):
        return "test_investigation_%d" % n
    institution = factory.Faker('word', ext_word_list=None)
    description = factory.Faker('sentence', nb_words=8)

    @factory.post_generation
    def values(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for value in extraced:
                self.values.add(value)
        else:
            for i in range(2):
                self.values.add(LinkedStrValFactory(type='metadata'))
    class Meta:
        model = Investigation

#Default: sample with a source step, one investigation, and 4 metadata
class SampleFactory(DjangoModelFactory):
    @factory.sequence
    def name(n):
        return "test_sample_%d" % n

    #foreign key
    @factory.post_generation
    def source_step(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.source_step = extracted
        else:
            self.source_step = StepFactory()

    @factory.post_generation
    def investigations(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for inv in extracted:
                self.investigations.add(inv)
        else:
            self.investigations.add(InvestigationFactory())

    @factory.post_generation
    def values(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for value in extracted:
                self.values.add(extracted)
        else:
            self.values.add(LinkedStrValFactory(type='metadata'))
            self.values.add(LinkedFloatValFactory(type='metadata'))
            self.values.add(LinkedIntValFactory(type='metadata'))
            self.values.add(LinkedDateTimeValFactory(type='metadata'))

    class Meta:
        model = Sample

"""############################################################################
###     Factories for Values                                                ###
###  Structure: Value factory abstract class.                               ###
###             Concrete factories for each val type.                       ###
###             Concrete factory for values linked to val type.             ###
############################################################################"""

#Abstract base factory for all values
class ValueFactory(DjangoModelFactory):
    name = factory.Faker('word', ext_word_list=None)
    object_id = factory.SelfAttribute('content_object.id')
    type='measure'
    content_type = factory.LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.content_object)
    )
    class Meta:
        exclude = ['content_object']
        abstract = True

"""### ### ### ### Factories for ValTypes  ### ### ### ### """
#Factory for StrVal Type
class StrValFactory(DjangoModelFactory):
    value = factory.Faker('word', ext_word_list=None)
    class Meta:
        model = StrVal

class IntValFactory(DjangoModelFactory):
    value = random.randint(0,500)
    class Meta:
        model = IntVal

class FloatValFactory(DjangoModelFactory):
    value = random.random() * random.randint(0,1000)
    class Meta:
        model = FloatVal

class DatetimeValFactory(DjangoModelFactory):
    value = factory.Faker('date_time')
    class Meta:
        model = DatetimeVal

class ResultValFactory(DjangoModelFactory):
    pass

"""### ### ### ### Factories for Values with linked valTypes ### ### ### ### """
#Factory for Value linke to StrVal
class LinkedStrValFactory(ValueFactory):
    content_object = factory.SubFactory(StrValFactory)
    class Meta:
        model = Value

class LinkedIntValFactory(ValueFactory):
    content_object = factory.SubFactory(IntValFactory)
    class Meta:
        model = Value

class LinkedFloatValFactory(ValueFactory):
    content_object = factory.SubFactory(FloatValFactory)
    class Meta:
        model = Value

class LinkedDateTimeValFactory(ValueFactory):
    content_object = factory.SubFactory(DatetimeValFactory)
    class Meta:
        model = Value

class LinkedResultValFactory(ValueFactory):
    pass

""" #########################################################################"""
