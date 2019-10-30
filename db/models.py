from collections import defaultdict

from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.aggregates import StringAgg

from celery import current_app
from combomethod import combomethod

import pandas as pd
import arrow
import uuid

from quorem.wiki import refresh_automated_report

User = get_user_model()

class Object(models.Model):
    base_name = "object"
    plural_name = "objects"
    id_field = "name"
    has_upstream = False
    search_set = None

    search_vector = SearchVectorField(blank=True,null=True)

    class Meta:
        abstract = True
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        if not self._state.adding:
            self.search_set = self.__class__.objects.filter(pk=self.pk)

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 self.base_name.capitalize() + ": " + \
                                 str(getattr(self, self.id_field))))

    @combomethod
    def with_value(receiver, name, value_type=None, linked_to=None, search_set=None, upstream=False, only=False):
        linkable_objects = ["samples", "features", "analyses", "steps", "processes",\
                            "results", "investigations"]
        if search_set is None:
            search_set = receiver._meta.model.objects.all()
        search_set = search_set.prefetch_related("values")
        if receiver.has_upstream & upstream:
            search_set = search_set.prefetch_related("all_upstream")
            upstream_set = receiver._meta.model.objects.filter(pk__in=search_set.values("all_upstream__pk").distinct())
            search_set = search_set.union(upstream_set).distinct()
        kwargs = {"values__name": name, "pk__in": search_set}
        if value_type is not None:
            kwargs["values__type"] = value_type
        #For some reason whittling down the search_set QuerySet doesn't work
        # So we have to go to the whole table
        if linked_to is not None:
            if isinstance(linked_to, list):
                for link in linked_to:
                    kwargs["values__" + link + "__isnull"] = False
                if only:
                    for obj in linkable_objects:
                        if "values__" + obj + "__isnull" not in kwargs:
                            kwargs["values__" + obj + "__isnull"] = True
            else:
                 kwargs = {"values__" + linked_to + "__isnull": False}
                 if only:
                     for obj in linkable_objects:
                         if obj != linked_to:
                             kwargs["values__" + obj + "__isnull"] = True
        hits = receiver._meta.model.objects.all()
        hits = hits.filter(**kwargs).distinct()
        if not hits.exists():
            return False
        else:
            return hits

    # In a combomethod, obj is either the class, or an instance
    @combomethod
    def with_metadata(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_value(name, "metadata", linked_to,
                                    search_set, upstream, only)

    @combomethod
    def with_measure(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_value(name, "measure", linked_to,
                                    search_set, upstream, only)

    @combomethod
    def with_parameter(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_value(name, "parameter", linked_to,
                                    search_set, upstream, only)

    # Default search methods, using only internal methods
    # At least one of these has to be overridden
    def related_samples(self, upstream=False):
        samples = Sample.objects.filter(source_step__in=self.related_steps(upstream=upstream)).distinct()
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=samples.values("all_upstream").distinct())
        return samples

    def related_processes(self, upstream=False):
        processes = Process.objects.filter(pk__in=self.related_steps(upstream=upstream).values("processes").distinct())
        if upstream:
            processes = processes | Process.objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_features(self):
        return Feature.objects.filter(samples__in=self.related_samples()).distinct()

    def related_steps(self, upstream=False):
        # Return the source_step for each sample
        steps = Step.objects.filter(pk__in=self.related_samples(upstream=upstream).values("source_step").distinct())
        if upstream:
            steps = steps | Step.objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_analyses(self):
        return Analysis.objects.filter(results__in=self.related_results()).distinct()

    def related_results(self, upstream=False):
        results = Result.objects.filter(samples__in=self.related_samples(upstream=upstream)).distinct()
        if upstream:
            results = results | Result.objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

    def related_investigations(self):
        return Investigation.objects.filter(samples__in=self.related_samples()).distinct()

    # Generic wrapper so we can get objects by string name instead of use getattr or something
    def related_objects(self, object_name, upstream=False):
        name_map = {"samples": self.related_samples,
                    "features": self.related_features,
                    "steps": self.related_steps,
                    "processes": self.related_processes,
                    "analyses": self.related_analyses,
                    "results": self.related_results,
                    "investigations": self.related_investigations}
        kwargs = {}
        if object_name in ["samples", "steps", "processes", "results"]:
            kwargs["upstream"] = upstream
        return name_map[object_name](**kwargs)

    def get_values(self, name, value_type):
        return self.values.filter(name=name, type=value_type)

    def get_upstream_values(self, name, value_type):
        if not self.has_upstream:
            return Value.objects.none()
        return Value.objects.filter(pk__in=self.all_upstream.values("values__pk"))

    @classmethod
    def get_queryset(cls, data):
        #data is a dict with {field_name: [name1,...],}
        # and uuid for results, id for all
        kwargs = {}
        for id_field in ["name", "uuid", "id"]:
            if cls.base_name + "_" + id_field in data:
                kwargs[id_field + "__in"] = data[cls.base_name + "_" + id_field]
        return cls._meta.model.objects.filter(**kwargs)

    # Creates bare minimum objects from the given data set
    @classmethod
    def initialize(cls, data):
        #data is a dict with {"field_name": [field data],}
        _id_fields = id_fields()
        req_fields = [ x for x in required_fields() if x.startswith(cls.base_name + "_") ]
        ref_fields = [ x for x in reference_fields() if x[0].startswith(cls.base_name + "_") ]
        single_ref_fields = [ x for x in single_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        many_ref_fields = [ x for x in many_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        # data validation
        for field_name in req_fields:
            if field_name not in data:
                raise ValueError("minimal_create: Missing required field name %s for object %s" % (field_name, cls.base_name))
            if (field_name in [x[0] for x in single_ref_fields]):
                if len(data[field_name]) > 1:
                    raise ValueError("minimal_create: Can only have one item in list for atomic field %s" % (field_name,))
        #This is all the objects that already exist
        cls_queryset = cls.get_queryset(data)
        if cls.base_name + "_" + cls.id_field in data:
            # If the id field is found in data, iterate over the ids
            for _id in data[cls.base_name + "_" + cls.id_field]:
                # Check if the id exists in the database, according to our previous query
                obj_queryset = cls_queryset.filter(**{cls.id_field: _id})
                if not obj_queryset.exists():
                    #Create the new one
                    kwargs = {cls.id_field: _id}
                    for field in req_fields:
                        django_field = field.replace(cls.base_name + "_", "")
                        if (django_field not in kwargs) and (django_field in data):
                            if field in [x[0] for x in ref_fields]:
                                # Grab it as a query
                                ref_model = [x[2] for x in ref_fields if x[0]==field][0]
                                ref_id = data[django_field]
                                if isinstance(ref_id, int):
                                    ref_id_field = "id"
                                else:
                                    ref_id_field = ref_model.id_field
                                try:
                                    obj = ref_model.objects.get(**{ref_id_field: ref_id})
                                except:
                                    raise ValueError("minimal_create: Cannot find referenced required %s '%s'" % (ref_model.base_name, ref_id))
                                kwargs[django_field] = obj
                            else:
                                kwargs[django_field] = data[django_field]
                        elif (django_field not in kwargs) and (django_field not in data):
                            raise ValueError("minimal_create: Missing required field %s in data" % (field,))
                    new_obj = cls()
                    for field in kwargs:
                        setattr(new_obj, field, kwargs[field])
                    new_obj.save()

    @classmethod
    def update(cls, data):
        _id_fields = id_fields()
        _all_fields = [ x for x in all_fields() if x.startswith(cls.base_name + "_") ]
        ref_fields = [ x for x in reference_fields() if x[0].startswith(cls.base_name + "_") ]
        single_ref_fields = [ x for x in single_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        many_ref_fields = [ x for x in many_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        # data validation
        for field_name in [x for x in _all_fields if x in data]:
            if (field_name in [x[0] for x in single_ref_fields]):
                if len(data[field_name]) > 1:
                    raise ValueError("update: Can only have one item in list for atomic field %s" % (field_name,))
        #This is all the objects that already exist
        cls_queryset = cls.get_queryset(data)
        # If the id field is found in data, iterate over the ids
        id_in_data = [ x for x in _id_fields if x in data]
        for id_field in id_in_data:
            for _id in data[id_field]:
                # Check if the id exists in the database, according to our previous query
                obj_queryset = cls_queryset.filter(**{id_field.replace(cls.base_name+"_",""): _id})
                if not obj_queryset.exists():
                    raise ValueError("update: %s %s not found when attempting to update. Did you use initialize?" % (cls.base_name,_id))
                else:
                    obj = obj_queryset.get()
                    for field in [x for x in _all_fields if (x not in _id_fields) and (x in data)]:
                        datum = getattr(obj, field.replace(cls.base_name+"_",""))
                        #Blank, feel free to overwrite
                        if field not in [x[0] for x in ref_fields]:
                            # If it isn't a reference, we just set the data
                            if (datum == "") or (datum == None):
                                setattr(obj, field.replace(cls.base_name+"_",""), data[field][0])
                            #elif datum != data[field][0]:
                            #    #TODO: set this as a warning? Overwrite?
                            #    pass
                        else:
                            # If it is a reference, we need to fetch it, then set it
                            # We also need to translate reverse fields into their ID fields
                            ref_model = [x[2] for x in ref_fields if x[0]==field][0]
                            for ref_id in data[field]:
                                if isinstance(ref_id, int):
                                    ref_id_field = "id"
                                else:
                                    ref_id_field = ref_model.id_field
                                try:
                                    ref_obj = ref_model.objects.get(**{ref_id_field: ref_id})
                                except:
                                    #TODO: Set this to a warning?
                                    raise ValueError("update: Cannot find referenced %s '%s'" % (ref_model.base_name, ref_id))
                                if field in [x[0] for x in many_ref_fields]:
                                    getattr(obj, field.replace(cls.base_name+"_","")).add(ref_obj)
                                    if field == cls.base_name + "_upstream":
                                        # In order to update the symmetrical
                                        # all_upstream/all_downstream fields
                                        # we add ref_obj to upstream and all_upstream
                                        # then we add all of ref_obj's upstream to
                                        # obj, and all of obj's downstream to
                                        # ref_obj's downstream
                                        # and then we have to update the cross
                                        # references of all other steps to one
                                        # another, saving as we let variables go
                                        obj.all_upstream.add(ref_obj)
                                        upstream_qs = ref_obj.all_upstream.all()
                                        downstream_qs = obj.all_downstream.all()
                                        obj.all_upstream.add(*upstream_qs)
                                        ref_obj.all_downstream.add(*downstream_qs)
                                        ref_obj.save()
                                        for down_obj in downstream_qs:
                                            for up_obj in upstream_qs:
                                                down_obj.all_upstream.add(up_obj)
                                            down_obj.save()
                                else:
                                    if (datum == "") or (datum == None):
                                        setattr(obj, field.replace(cls.base_name+"_",""), ref_obj)
                                        #TODO: Set else to a warning? Overwrite?
                        #elif datum != data[field]:
                        #    pass
                            #TODO: Add a warning that it didn't overwrite
                    obj.save()

class Investigation(Object):
    base_name = "investigation"
    plural_name = "investigations"

    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255)
    description = models.TextField()

    values = models.ManyToManyField('Value', related_name="investigations", blank=True)
    categories = models.ManyToManyField('Category', related_name='investigations', blank=True)

    @classmethod
    def update_search_vector(self):
        sv =( SearchVector('name', weight='A') +
             SearchVector('description', weight='B') +
             SearchVector('institution', weight='C') )
        Investigation.objects.update(search_vector = sv)
#        refresh_automated_report("investigation")
#        refresh_automated_report("investigation", pk=self.pk)

    def related_samples(self, upstream=False):
        # SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples


class Feature(Object):
    base_name = "feature"
    plural_name = "features"

    name = models.CharField(max_length=255, verbose_name="Name")
    sequence = models.TextField(null=True, blank=True)
    annotations = models.ManyToManyField('Value', related_name='+', blank=True)
    first_result = models.ForeignKey('Result', on_delete=models.CASCADE, blank=True, null=True)
    samples = models.ManyToManyField('Sample', related_name='features', blank=True)

    values = models.ManyToManyField('Value', related_name="features", blank=True)
    categories = models.ManyToManyField('Category', related_name="features", blank=True)

    @classmethod
    def update_search_vector(self):
        Feature.objects.update(
            search_vector = (SearchVector('name', weight= 'A') +
                             SearchVector(StringAgg('annotations__str', delimiter=' '), weight='B'))
        )

    def related_samples(self, upstream=False):
        #SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_results(self, upstream=False):
        # SQL Depth: 2
        results = self.results.all()
        if upstream:
            results = results | Result.objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

class Sample(Object):
    base_name = "sample"
    plural_name = "samples"

    has_upstream = True

    name = models.CharField(max_length=255,unique=True)
    investigations = models.ManyToManyField('Investigation', related_name='samples', blank=True)  # fk 2
    source_step = models.ForeignKey('Step', related_name='samples', on_delete=models.CASCADE, blank=True, null=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    # A cache of all of the upstream Samples up the chain
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="samples", blank=True)
    categories = models.ManyToManyField('Category', related_name='samples', blank=True)


    @classmethod
    def update_search_vector(self):
        Sample.objects.update(
            search_vector = (SearchVector('name', weight= 'A') #+
                             # Should be investigation name, not pk.
                             # SearchVector('investigation', weight = 'B')
                             )
        )
#        refresh_automated_report("sample", pk=self.pk)

    def related_investigations(self):
        return self.investigations.all()

    def related_features(self):
        return self.features.all()

    def related_steps(self, upstream=False):
        steps = Step.objects.filter(pk=self.source_step.pk)
        if upstream:
            steps = steps | Step.objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_results(self, upstream=False):
        # SQL Depth: 1
        results = self.results.all()
        if upstream:
            results = results | Result.objects.filter(pk__in=results.values("all_upstream").distinct())
        return results.distinct()

class Process(Object):
    base_name = "process"
    plural_name = "processes"

    has_upstream = True

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    citation = models.TextField(blank=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name="downstream", blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="processes", blank=True)
    categories = models.ManyToManyField('Category', related_name="processes", blank=True)

    @classmethod
    def update_search_vector(self):
        Process.objects.update(
            search_vector = (SearchVector('name', weight='A') +
                             SearchVector('citation', weight='B') +
                             SearchVector('description', weight='C'))
        )

    def related_steps(self, upstream=False):
        steps = self.steps.all()
        if upstream:
            steps = steps | Step.objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_analyses(self):
        return self.analyses.all()

class Step(Object):
    base_name = "step"
    plural_name = "steps"

    has_upstream = True

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    processes = models.ManyToManyField('Process', related_name='steps', blank=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)
    values = models.ManyToManyField('Value', related_name='steps', blank=True)
    categories = models.ManyToManyField('Category', related_name='steps', blank=True)

    @classmethod
    def update_search_vector(self):
        Step.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('description', weight='B'))
        )

    def related_samples(self, upstream=False):
        samples = Sample.objects.filter(source_step__pk=self.pk)
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_processes(self, upstream=False):
        processes = self.processes.all()
        if upstream:
            processes = processes | Process.objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_analyses(self):
        # SQL Depth: 2
        return Analysis.objects.filter(extra_steps__pk=self.pk,
                                       process__in=self.related_processes()).distinct()

    def related_results(self, upstream=False):
        # Results ejected from this step
        results = Result.objects.filter(source_step__pk=self.pk)
        if upstream:
            results = results | Result.objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

class Analysis(Object):
    base_name = "analysis"
    plural_name = "analyses"

    # This is an instantiation/run of a Process and its Steps
    name = models.CharField(max_length=255)
    date = models.DateTimeField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    process = models.ForeignKey('Process', on_delete=models.CASCADE)
    # Just in case this analysis had any extra steps, they can be defined and tagged here
    # outside of a Process
    extra_steps = models.ManyToManyField('Step', blank=True)
    # Run-specific parameters can go in here, but I guess Measures can too
    values = models.ManyToManyField('Value', related_name='analyses', blank=True)
    categories = models.ManyToManyField('Category', related_name='analyses', blank=True)

    @classmethod
    def update_search_vector(self):
        Analysis.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('date', weight='B') +
                            SearchVector('location', weight='C'))
        )

    def related_samples(self, upstream=False):
        # All samples for all Results coming out of this Analysis
        samples = Sample.objects.filter(pk__in=self.results.values("samples").distinct())
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_steps(self, upstream=False):
        steps = self.extra_steps.all() | self.process.steps.all()
        if upstream:
            steps = steps | Step.objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_processes(self, upstream=False):
        results = Process.objects.filter(pk=self.process.pk)
        if upstream:
            processes = processes | Process.objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_results(self, upstream=False):
        results = self.results.all()
        if upstream:
            results = results | Result.objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

class Result(Object):
    """
    Some kind of result from an analysis
    """
    base_name = "result"
    plural_name = "results"
    id_field = "uuid"
    has_upstream = True

    list_display = ('source', 'type', 'source_step', 'processes', 'samples', 'values', 'uuid')
    uuid = models.UUIDField(unique=True) #For QIIME2 results, this is the artifact UUID
    file = models.ForeignKey('File', on_delete=models.CASCADE, verbose_name="Result File Name", blank=True, null=True)
    source = models.CharField(max_length=255, verbose_name="Source Software/Instrument", blank=True, null=True)
    type = models.CharField(max_length=255, verbose_name="Result Type", blank=True, null=True)
    analysis = models.ForeignKey('Analysis', related_name='results', on_delete=models.CASCADE)
    # This process result is from this step
    source_step = models.ForeignKey('Step', on_delete=models.CASCADE, verbose_name="Source Step", blank=True, null=True)
    # Samples that this thing is the result for
    samples = models.ManyToManyField('Sample', related_name='results', verbose_name="Samples", blank=True)
    features = models.ManyToManyField('Feature', related_name='results', verbose_name="Features", blank=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)
    #from_provenance = models.BooleanField(default=False)

    values = models.ManyToManyField('Value', related_name="results", blank=True)
    categories = models.ManyToManyField('Category', related_name='results', blank=True)

    def __str__(self):
        return str(self.uuid)

    @classmethod
    def update_search_vector(self):
        Result.objects.update(
            search_vector= (SearchVector('source', weight='A') +
                            SearchVector('type', weight='B') +
                            SearchVector('uuid', weight='C'))
        )

    def related_samples(self, upstream=False):
        samples = self.samples.all()
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_features(self):
        return self.features.all()

    def related_steps(self, upstream=False):
        if not self.source_step:
            return Step.objects.none()
        steps = Step.objects.filter(pk=self.source_step.pk)
        if upstream:
            steps = steps | Step.objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_processes(self, upstream=False):
        processes = Process.objects.filter(pk=self.analysis.process.pk)
        if upstream:
            processes = processes | Process.objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_analyses(self):
        return Analysis.objects.filter(pk=self.analysis.pk)


# This allows the users to define a process as they wish
# Could be split into "wet-lab process" and "computational process"
# or alternatively, "amplicon", "metagenomics", "metabolomics", "physical chemistry", etc.
class Category(models.Model):
    base_name = "category"
    plural_name = "categories"

    #This tracks which model this category associates with
    category_of = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'category_of'], name='Only one category of each name per model')
            ]
    def __str__(self):
        return self.name

### Key-Value storage for objects

class Value(models.Model):
    base_name = "value"
    plural_name = "values"

    default_date_format = "DD/MM/YYYY"

    PARAMETER = 'parameter'
    METADATA = 'metadata'
    MEASURE = 'measure'
    VALUE_TYPES = (
            (PARAMETER, 'Parameter'),
            (METADATA, 'Metadata'),
            (MEASURE, 'Measure'))
    name = models.CharField(max_length=512)
    type = models.CharField(max_length=9, choices=VALUE_TYPES)
    # This generic relation links to a polymorphic Val class
    # Allowing Value to be str, int, float, datetime, etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    linkable_objects = ["samples", "features", "analyses", "steps", \
                        "processes", "results", "investigations"]

    search_vector = SearchVectorField(null=True)

    def __str__(self):
        return self.name + ": " + str(self.content_object.value)

    @classmethod
    def add_values(cls, table):
        value_models = defaultdict(dict)
        _id_fields = id_fields()
        _all_fields = all_fields()
        # First pre-fetch all the objects in data in a dict of QuerySets
        recs = table[[x for x in table.columns if x in _id_fields]].melt().dropna().drop_duplicates().to_records(index=False)
        id_data = defaultdict(list)
        for field, datum in recs:
            id_data[field].append(datum)
        object_querysets = {}
        for Obj in object_list:
            object_querysets[Obj.base_name] = Obj.get_queryset(id_data).prefetch_related("values")
        # Commit each value, row by row (the only way, really)
        for index, series in table.iterrows():
            series = series.dropna()
            value_name = series["value_name"]
            value_type = series["value_type"]
            value = str(series["value"])
            value_targets = [series[x] for x in series.index if x.startswith("value_target")]
            link_data = defaultdict(set)
            for field in series.index:
                if field in _id_fields:
                    link_data[field].add(series[field])
            kwargs = {"values__name": value_name, "values__type": value_type}
            valargs = {"name": value_name, "type": value_type}
            for Obj in object_list:
                if (Obj.base_name in value_targets) or (Obj.plural_name in value_targets):
                    kwargs["values__" + Obj.plural_name + "__isnull"] = False
                    valargs[Obj.plural_name + "__isnull"] = False
                else:
                    kwargs["values__" + Obj.plural_name + "__isnull"] = True
                    valargs[Obj.plural_name + "__isnull"] = True
            # Filter for Values that match the signature
            value_qs = Value.objects.all()
            for target in value_targets:
                qs = object_querysets[target]
                id_field = qs.model.id_field
                base_name = qs.model.base_name
                kwargs[id_field + "__in"] = list(link_data[base_name + "_" + id_field])
                qs = qs.filter(**kwargs)
                # Keep track of the values in all of these
                valargs["pk__in"] = qs.values("values").distinct()
                value_qs = value_qs.filter(**valargs)
                valargs = {}
                # We need to check if it's linked to the exact right objects
                # and if not, we can create it
            found = False
            queryset_list = [ object_querysets[Obj.base_name].filter(**{Obj.id_field+"__in": link_data[Obj.base_name+"_"+Obj.id_field] }) for Obj in object_list ]
            for value_obj in value_qs:
                ##This can probably be replaced with fancier querysets above
                if value_obj.linked_to(queryset_list):
                    found = True
                    #TODO: Check if the value is equal and overwrite and/or raise a warning?
                    break
            if found:
                continue # Go to the next row
            # We didn't find it, proceed to create
            if value_name in value_models[value_type]:
                val_model = value_models[value_type][value_name]
            else:
                val_model = cls.infer_type(value_name, value_type, value)
                value_models[value_type][value_name] = val_model
            new_val = val_model()
            new_val.value = val_model.cast_function(value)
            new_val.save()
            new_Value = Value()
            new_Value.name = value_name
            new_Value.type = value_type
            new_Value.content_object = new_val
            new_Value.save()
            for qs in queryset_list:
                getattr(new_Value, qs.model.plural_name).add(*qs)

    def linked_to(self, queryset_list, only=True):
        #Queryset list is a list of querysets to check if they are linked
        # Check that every object in the list is linked to the value (and nothing else is)
        links = self.get_links()
        for qs in queryset_list:
            if (qs.model.plural_name not in links) and (qs.exists()):
                return False
            elif (qs.model.plural_name not in links):
                continue
            if only and len(qs) != len(links[qs.model.plural_name]):
                return False
            for _id in qs.values(qs.model.id_field).distinct():
                if _id[qs.model.id_field] not in links[qs.model.plural_name]:
                    return False
                else:
                    links[qs.model.plural_name].pop(links[qs.model.plural_name].index(_id[qs.model.id_field]))
        if only:
            for field in links:
                if len(links[field]) > 0:
                    return False
        return True

    def get_links(self):
        linked_to = [ (Obj.plural_name, Obj) for Obj in object_list if getattr(self, Obj.plural_name).exists() ]
        self_link_ids = {}
        for field, model in linked_to:
            ids = list(getattr(self, field).values_list(model.id_field, flat=True).distinct())
            self_link_ids[field] = ids
        return self_link_ids

    def related_values(self, name, value_type, linked_to, upstream=False, only=False):
        #Reach out to find each of the relevant related objects linked to
        #everything tied to this Value, and then search those sets
        records = [] # Format (self.name, self_value, name, val.content_object.value, B_id)
        self_links = self.get_links()
        self_value = self.content_object.value
        values = Value.objects.none()
        for link_field in linked_to:
            queryset = getattr(self, link_field).none()
            for field in self.linkable_objects:
                if field is not link_field:
                    search_set = getattr(self, field).all()
                    #TODO: make related_* functions handle QuerySets instead of just self
                    for obj in search_set:
                        queryset = queryset | obj.related_objects(link_field, upstream)
            if queryset.exists():
                model = queryset[0]._meta.model
                related_with_target = model.with_value(name, value_type,
                                         linked_to, queryset, upstream, only)
                if related_with_target != False:
                    for obj in related_with_target:
                        values = values | obj.get_values(name=name, type=value_type)
        return values

    def upstream_values(self, name, value_type, linked_to, only=False, include_self=True):
        # Search strictly upstream objects of the links of this one
        pass

    def export_values(self, values):
        if not values.exists():
            return pd.DataFrame.from_records([])
        records = []
        self_links = self.get_links()
        self_val = self.content_object.value
        values = values.prefetch_related("content_object")
        values = values.prefetch_related(*self.linkable_objects)
        for val in values:
            rec = list(self_links.values())
            rec.extend([self.name, self_val, val.name, val.content_object.value])
            val_links = val.get_links()
            rec.extend(list(val_links.values()))
            records.append(rec)
        cols = []
        cols.extend(["source_" + x for x in list(self_links.keys())])
        cols.extend(["source_value_name", "source_value", "related_value_name", "related_value"])
        cols.extend(["related_" + x for x in list(val_links.keys())])
        return pd.DataFrame.from_records(records, columns=cols)

    @classmethod
    def relate_value_sets(cls, A, B):
        # Link all Values in A to all Values in B, if possible
        pass

    @classmethod
    def disambiguate(cls, name, value_type=None, linked_to=None, only=False, return_queryset=False):
        #Like most functions, try to kick out as soon as we know there's an ambiguity we can resolve
        qs = Value.objects.filter(name=name)
        if value_type is not None:
            qs = qs.filter(type=value_type)
        qs = qs.prefetch_related("samples","features","analyses",
                                 "investigations","steps","processes","results")
        if linked_to is not None:
            if isinstance(linked_to, list):
                kwargs = {}
                for link in linked_to:
                    kwargs[link + "__isnull"] = False
                if only:
                    for obj in self.linkable_objects:
                        if obj + "__isnull" not in kwargs:
                            kwargs[obj + "__isnull"] = True
                qs = qs.filter(**kwargs)
            else:
                 kwargs = {linked_to + "__isnull": False}
                 if only:
                     for obj in self.linkable_objects:
                         if obj != linked_to:
                             kwargs[obj + "__isnull"] = True
                 qs = qs.filter(**kwargs)
        values = qs
        qs = qs.annotate(samples_count=models.Count("samples"),
                         features_count=models.Count("features"),
                         analyses_count=models.Count("analyses"),
                         investigations_count=models.Count("investigations"),
                         results_count=models.Count("results"),
                         processes_count=models.Count("processes"),
                         steps_count=models.Count("steps"))
        qs = qs.values("type","samples_count","features_count",
                       "analyses_count","investigations_count","results_count",
                       "processes_count","steps_count")
        qs = qs.distinct()
        #Unambiguous if 1 signature, or vacuously if not in DB at all
        if (len(qs) <= 1):
            if return_queryset:
                return values
            else:
                return True
        else:
            #Collect ambiguities
            if return_queryset:
                return values
            signatures = list(qs)
            signature_dict = defaultdict(set)
            for signature in signatures:
                link_list = []
                for key in signature:
                    if key.endswith("_count") and (signature[key]>0):
                        link_list.append(key.split("_")[0])
                if link_list:
                    signature_dict[signature["type"]].add(tuple(link_list))
            return signature_dict

    @classmethod
    def infer_type(cls, value_name, value_type, value=None):
        found_types = ContentType.objects.filter(pk__in=Value.objects.filter(name=value_name,
                                                 type=value_type).only("content_type").values("content_type")).distinct()
        if len(found_types) > 1:
            raise DuplicateTypeError("Two types found for value name %s of \
                                      type %s" % (self.id_field, self.vtype))
        elif len(found_types) == 1:
            return found_types[0].model_class()
        elif value:
            strvalue = str(value)
            try:
                arrow.get(strvalue, cls.default_date_format)
                return DatetimeVal
            except arrow.parser.ParserError:
                pass
            try:
                uuid.UUID(strvalue)
                return ResultVal
            except ValueError:
                pass
            try:
                int(strvalue)
                return IntVal
            except ValueError:
                pass
            try:
                float(strvalue)
                return FloatVal
            except ValueError:
                pass
            # Default value
            return StrVal
        else:
            return None

    @classmethod
    def update_search_vector(self):
        Value.objects.update(
            search_vector= (SearchVector('name', weight='A') +
#                            SearchVector('', weight='B') +
                            SearchVector('value_type', weight='B'))
        )


class StrVal(models.Model):
    type_name = "str"
    cast_function = str
    value = models.TextField()
    val_obj = GenericRelation(Value,related_query_name=type_name)

class IntVal(models.Model):
    type_name = "int"
    cast_function = int
    value = models.IntegerField()
    val_obj = GenericRelation(Value, related_query_name=type_name)

class FloatVal(models.Model):
    type_name =  "float"
    cast_function = float
    value = models.FloatField()
    val_obj = GenericRelation(Value, related_query_name=type_name)

class DatetimeVal(models.Model):
    type_name = "datetime"
    cast_function = arrow.get
    value = models.DateTimeField()
    val_obj = GenericRelation(Value, related_query_name=type_name)

#This is if the input parameter is another result, ie. another artifact searched by UUID
class ResultVal(models.Model):
    type_name = "result"
    cast_function = uuid.UUID
    value = models.ForeignKey('Result', on_delete=models.CASCADE)
    val_obj = GenericRelation(Value, related_query_name=type_name)
    def __str__(self):
        return value.name + ": " + value.type



object_list = [Investigation, Sample, Feature, Step, Process, \
               Analysis, Result]

#CAUTION: List comprehensions ahead!!

def all_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if (x.name not in ["search_vector", "content_type", \
                     "all_upstream", "object_id", "category_of"]) and \
                     x.concrete] for Obj in object_list] for item in sublist]

def id_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if (x.name in ["id", "name", "uuid"]) and (x.concrete)] \
                         for Obj in object_list] for item in sublist]

def required_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if x.name not in ["search_vector", "content_type", \
                                    "object_id", "category_of"] and x.concrete \
                     and hasattr(x,"blank") and not x.blank] \
                         for Obj in object_list] for item in sublist]

def reference_fields():
    # Returns tuples of the field name, from model, and to model
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, \
                                                      x.model, \
                                                      x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream", "content_type", \
                 "object_id", "category_of"] and x.concrete and x.is_relation] \
                 for Obj in object_list] for item in sublist]

def single_reference_fields():
    # Returns tuples of the field name, from model, and to model
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, \
                                                      x.model, \
                                                      x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream", "content_type", \
                 "object_id", "category_of"] and x.concrete and x.many_to_one] \
                 for Obj in object_list] for item in sublist]


def many_reference_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, x.model, x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream"] \
                 and x.concrete and (x.many_to_many or x.one_to_many)] for Obj in object_list] \
                 for item in sublist]

class UserProfile(models.Model):
    #userprofile doesnt have a search vector bc it shouldn tbe searched.
    user = models.ForeignKey(User, on_delete=models.CASCADE, unique=True)

    @classmethod
    def create(cls, user):
        userprofile = cls(user=user)
        return userprofile
    def __str__(self):
        return self.user.email

#a class for mail messages sent to users.
class UserMail(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now=False, auto_now_add=True)
    title = models.TextField()
    message = models.TextField()
    #mail is oviously not read when it's first created
    read = models.BooleanField(default = False)

class File(models.Model):
    base_name = "file"
    plural_name = "files"
    STATUS_CHOICES = (
        ('P', "Processing"),
        ('S', "Success"),
        ('E', "Error")
    )
    TYPE_CHOICES = (
        ('S', 'Spreadsheet'),
        ('A', 'Artifact'))
    userprofile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name='Uploader')
    upload_file = models.FileField(upload_to="upload/")
    upload_status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    upload_type = models.CharField(max_length=1, choices=TYPE_CHOICES)
    #Should upload files be indexed by the search??
    #search_vector = SearchVectorField(null=True)

    def __str__(self):
        return "UserProfile: {0}, UploadFile: {1}".format(self.userprofile, self.upload_file)

    def save(self, *args, **kwargs):
        self.upload_status = 'P'
        super().save(*args, **kwargs)
        #Call to celery, without importing from tasks.py (avoids circular import)
    #    current_app.send_task('db.tasks.react_to_file', (self.pk,))
        #output = result.collect()
        ##    print(i)
    def update(self, *args, **kwargs):
        super().save(*args, **kwargs)

class UploadMessage(models.Model):
    """
    Store messages for file uploads.
    """
    file = models.ForeignKey(File, on_delete=models.CASCADE, verbose_name='Uploaded File')
    error_message = models.CharField(max_length = 1000, null=True)


##Function for search.
##Search returns a list of dicts. Get the models from the dicts.
def load_mixed_objects(dicts,model_keys):
    #dicts are expected to have 'pk', 'rank', 'type'
    to_fetch = {}
    for d in dicts:
        to_fetch.setdefault(d['otype'], set()).add(d['pk'])
    fetched = {}

    for key, model, ui_string in model_keys:
        #disregard the ui_string variable. It's for frontend convenience.
        ids = to_fetch.get(key) or []
        objects = model.objects.filter(pk__in=ids)
        for obj in objects:
            fetched[(key, obj.pk)] = obj
    #return the list in the same otder as dicts arg
    to_return = []
    for d in dicts:
        item = fetched.get((d['otype'], d['pk'])) or None
        if item:
                item.original_dict = d
        to_return.append(item)

    return to_return
