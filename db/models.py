from collections import defaultdict
import logging
import itertools

from django.db import models
from django.core import files
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.aggregates import StringAgg

from celery import current_app
from combomethod import combomethod

import pandas as pd
import numpy as np
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
        return self.values.filter(name=name, value=value_type)

    def get_upstream_values(self, name, value_type):
        if not self.has_upstream:
            return Value.objects.none()
        return Value.objects.filter(pk__in=self.all_upstream.values("values__pk"))

    @classmethod
    def get_id_fields(cls):
        return [cls.base_name + "_" + cls.id_field, cls.base_name + "_id"]

    @classmethod
    def get_value_fields(cls):
        return [cls.plural_name + "__" + cls.id_field, cls.plural_name + "__id"]

    @classmethod
    def get_queryset(cls, data):
        #data is a dict with {field_name: [name1,...],}
        # and uuid for results, id for all
        if (not data):
            return cls._meta.model.objects.none()
        kwargs = {}
        for id_field in [cls.id_field, "id"]:
            if cls.base_name + "_" + id_field in data:
                kwargs[id_field + "__in"] = data[cls.base_name + "_" + id_field]
        if not kwargs:
            return cls._meta.model.objects.none()
        return cls._meta.model.objects.filter(**kwargs)

    # Creates bare minimum objects from the given data set
    @classmethod
    def initialize(cls, data, log=None):
        #data is a dict with {"field_name": [field data],}
        _id_fields = id_fields()
        req_fields = [ x for x in required_fields() if x.startswith(cls.base_name + "_") ]
        ref_fields = [ x for x in reference_fields() if x[0].startswith(cls.base_name + "_") ]
        single_ref_fields = [ x[0] for x in single_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        many_ref_fields = [ x for x in many_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        ref_proxies = reference_proxies()
        cls_proxies = [x for x in ref_proxies if ref_proxies[x][0].startswith(cls.base_name)]
        ids = []
        cls_proxy = False
        if (cls.base_name + "_id" not in data) and \
           (cls.base_name + "_" + cls.id_field not in data):
                cls_proxy_fields = []
                for proxy_field in cls_proxies:
                    if proxy_field in data:
                        cls_proxy = True
                        cls_proxy_fields.append(proxy_field)
                if not cls_proxy:
                    #Nothing to do for this class, so bail
                    return
       # Fast non-database data validation:
        required_proxies = dict()
        for field_name in req_fields:
            if (field_name not in data) and (field_name in ref_proxies):
                #Search for a proxy field
                proxy = False
                for proxy_field in ref_proxies[field_name]:
                    if proxy_field in data:
                        proxy = True
                        required_proxies[field_name] = proxy_field
                # If no proxy is present, raise error
                if not proxy:
                    raise ValueError("initialize %s: Missing required field name %s for object %s and no proxies found" % (cls.base_name, field_name, cls.base_name))
            elif field_name not in data:
                    raise ValueError("initialize %s: Missing required field name %s for object %s" % (cls.base_name, field_name, cls.base_name))
            if (field_name in [x[0] for x in single_ref_fields]):
                if len(data[field_name]) > 1:
                    raise ValueError("initialize %s: Can only have one item in list for atomic field %s" % (cls.base_name, field_name,))
        assert (cls.base_name + "_id" in data) or (cls.base_name + "_" + cls.id_field in data) or (cls_proxy)
        if cls.base_name + "_id" in data:
            ids.extend(data[cls.base_name + "_id"])
        if cls.base_name + "_" + cls.id_field in data:
            ids.extend(data[cls.base_name + "_" + cls.id_field])
        if cls_proxy:
            for cls_proxy_field in cls_proxy_fields:
                ids.extend(data[cls_proxy_field])
        #This should be the only true database hit for each call of this, unless references have to be pulled
        cls_queryset = cls.get_queryset(data)
        found_ids = [str(x) for x in cls_queryset.values_list(cls.id_field, flat=True)]
        # If the id field is found in data, iterate over the ids
        ref_objects = defaultdict(dict)
        for _id in ids:
            # Check if the id exists in the database, according to our previous query
            if isinstance(_id, int):
                # Nothing to do for an initialize
                continue
            _id = str(_id)
            if not _id in found_ids:
                #Create the new one
                kwargs = {cls.id_field: _id}
                for field in req_fields:
                    django_field = field.split("_")[1]
                    if field in single_ref_fields:
                        if field in required_proxies:
                            ref_id = data[required_proxies[field]][0]
                        else:
                            ref_id = data[field][0]
                        # Grab it as a query
                        ref_model = [x[2] for x in ref_fields if x[0]==field][0]
                        if (ref_id in ref_objects[ref_model.base_name]):
                            obj = ref_objects[ref_model.base_name][ref_id]
                        else:
                            if isinstance(ref_id, int):
                                ref_id_field = "id"
                            else:
                                ref_id_field = ref_model.id_field
                            try:
                                obj = ref_model.objects.get(**{ref_id_field: ref_id})
                                ref_objects[ref_model.base_name][ref_id] = obj
                            except:
                                raise ValueError("initialize %s: Cannot find referenced required %s '%s'" % (cls.base_name, ref_model.base_name, ref_id))
                        kwargs[django_field] = obj
                    elif django_field != cls.id_field:
                        kwargs[django_field] = data[field][0]
                new_obj = cls()
                for field in kwargs:
                    setattr(new_obj, field, kwargs[field])
                new_obj.save()

    @classmethod
    def update(cls, data, log=None):
        _id_fields = id_fields()
        _all_fields = [ x for x in all_fields() if x.startswith(cls.base_name + "_") ]
        ref_fields = [ x for x in reference_fields() if x[0].startswith(cls.base_name + "_") ]
        single_ref_fields = [ x for x in single_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        many_ref_fields = [ x for x in many_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        ref_proxies = reference_proxies()
        # data validation
        for field_name in [x for x in _all_fields if x in data]:
            if (field_name in single_ref_fields):
                if len(data[field_name]) > 1:
                    raise ValueError("update: Can only have one item in list for atomic field %s" % (field_name,))
        #This is all the objects that already exist
        cls_queryset = cls.get_queryset(data)
        # If the id field is found in data, iterate over the ids
        obj_id_in_data = [ x for x in _id_fields if x.startswith(cls.base_name) and (x in data)]
        for id_field in obj_id_in_data:
            for _id in data[id_field]:
                # Check if the id exists in the database, according to our previous query
                obj_queryset = cls_queryset.filter(**{id_field.split("_")[1]: _id})
                if not obj_queryset.exists():
                    raise ValueError("update: %s %s not found when attempting to update. Did you use initialize?" % (cls.base_name,_id))
                else:
                    obj = obj_queryset.get()
                    for field in [x for x in _all_fields if (x not in _id_fields) and (x.startswith(cls.base_name))]:
                        proxy_fields = []
                        if (field not in data) and (field in ref_proxies) and (not field.endswith("_upstream")):
                            for proxy in ref_proxies[field]:
                                if proxy in data:
                                    proxy_fields.append(proxy)
                            if (field in required_fields()) and (len(proxy_fields) == 0):
                                raise ValueError("Field %s required and not found, and no proxy ID fields found." % (field,))
                        db_datum = getattr(obj, field.replace(cls.base_name+"_",""))
                        #Blank, feel free to overwrite
                        if (field not in [x[0] for x in ref_fields]) and (field in data):
                            # If it isn't a reference, we just set the data
                            if (db_datum == "") or (db_datum == None):
                                setattr(obj, field.replace(cls.base_name+"_",""), data[field][0])
                            #elif datum != data[field][0]:
                            #    #TODO: set this as a warning? Overwrite?
                            #    pass
                        elif (field in [x[0] for x in ref_fields]):
                            # If it is a reference, we need to fetch it, then set it
                            # We also need to translate reverse fields into their ID fields
                            ref_model = [x[2] for x in ref_fields if x[0]==field][0]
                            proxy_fields.append(field)
                            for search_field in proxy_fields:
                                if search_field in data:
                                    for ref_id in data[search_field]:
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
                                            if (db_datum == "") or (db_datum == None):
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

    def get_parameters(self, steps=[]):
        # Get the parameters for this Analysis and all its steps
        # including the extra ones
        parameters = defaultdict(dict)
        if steps != []:
            steps = Step.objects.filter(name__in=steps)
        else:
            steps = self.steps
        for step in steps.all():
            for queryset in [step.values.filter(processes__isnull=True,
                                                analyses__isnull=True,
                                                results__isnull=True),
                             self.values.filter(steps=step)]:
                for value in queryset.filter(steps=step, type="parameter"):
                    parameters[step.name][value.name] = value.content_object.value
        return parameters

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

    def get_parameters(self):
        # Get the parameters for this Result, with respect to its source step
        parameters = {}
        for value in self.values.filter(type="parameter",
                                        results__isnull=True,
                                        analyses__isnull=True,
                                        processes__isnull=True):
            parameters[value.name] = value.content_object.value
        return parameters

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
    process = models.ForeignKey('Process', on_delete=models.CASCADE, related_name='analyses')
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

    def get_parameters(self, steps=[]):
        # Get the parameters for this Analysis and all its steps
        # including the extra ones
        parameters = defaultdict(dict)
        if steps != []:
            steps = [Step.objects.filter(name__in=steps)]
        else:
            steps = [self.process.steps, self.extra_steps]
        for step_queryset in steps:
            for step in step_queryset.all():
                for queryset in [step.values.filter(processes__isnull=True,
                                                    analyses__isnull=True,
                                                    results__isnull=True),
                                 self.process.values.filter(steps=step),
                                 self.values.filter(steps=step)]:
                    for value in queryset.filter(type="parameter"):
                        parameters[step.name][value.name] = value.content_object.value
        return parameters

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

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 self.type + " from " + self.source_step.name))

    @classmethod
    def update_search_vector(self):
        Result.objects.update(
            search_vector= (SearchVector('source', weight='A') +
                            SearchVector('type', weight='B') +
                            SearchVector('uuid', weight='C'))
        )

    def get_parameters(self):
        # Get the parameters for this Result, with respect to its source step
        parameters = {}
        for queryset in [self.source_step.values.filter(results=self),
                         self.analysis.process.values,
                         self.analysis.values,
                         self.values]:
            for value in queryset.filter(steps=self.source_step, type="parameter"):
                parameters[value.name] = value.content_object.value
        return parameters

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
    def create_value(cls, value_name, value_type, value, linked_to=[], value_model=None):
        if value_model == None:
            value_model = cls.infer_type(value_name, value_type, value)
        new_val = value_model()
        try:
            new_val.value = value_model.cast_function(value)
        except Result.DoesNotExist:
            print("Warning, could not find Result %s, abandoning adding %s %s" % (str(value), value_type, value_name))
            return
        new_val.save()
        new_Value = Value()
        new_Value.name = value_name
        new_Value.type = value_type
        new_Value.content_object = new_val
        new_Value.save()
        for qs in linked_to:
            if qs.exists():
                getattr(new_Value, qs.model.plural_name).add(*qs)

    @classmethod
    def _table_value_targets(cls, table, unique=False):
            value_target_combinations = list(table[[x for x in table.columns if x.startswith("value_target")]].drop_duplicates().agg(lambda x: list(x.dropna()), axis=1))
            if unique:
                unique_targets = set()
                ut_add = unique_targets.add
                for element in itertools.filterfalse(unique_targets.__contains__, [y for x in value_target_combinations for y in x]):
                    ut_add(element)
                unique_targets = list(unique_targets)
                return unique_targets
            return value_target_combinations

    @classmethod
    def add_parameters(cls, table, database_table, log=None):
        print("Adding parameters")
        # PARAMETERS
        # Heuristics:
        # - All Parameters must be linked to a Step, as all parameters are relative to a Step
        # - If it is an Analysis or Process being linked, we speed it up by specifying steps=[source_step]
        # - Sort measures by Step
        # - Start with things linked only to the Step, then Step+Process, Step+Analysis, Step+Result, inserting new Values only when needed

        #Now that we've aggregated all the parameter data, we want to go top-down so we don't miss any Values in the lower objects
        unique_targets = cls._table_value_targets(table, unique=True)
        # Use this dict to track all of the levels of input parameters
        parameter_data = {"process": {"analysis": {"result": {"parameters" : defaultdict(lambda: defaultdict(dict))},
                                                     "parameters": defaultdict(lambda: defaultdict(dict))},
                                        "parameters": defaultdict(lambda: defaultdict(dict))},
                          "parameters": defaultdict(dict)}
        # Organize the data by step (all parameters attached to a step)
        print("Organizing data")
        for step in table["step_name"].unique():
             subtable = table[table["step_name"]==step]
             subtable = subtable[[x for x in table.columns if \
                                  (x in ["value", "value_name"]) or \
                                   x.startswith("value_target") or \
                                  (x.split("_")[0] in unique_targets) and\
                                   (x in id_fields())]].drop_duplicates()
             row_targets = cls._table_value_targets(subtable, unique=True)
             for ind, series in subtable.iterrows():
                 if len(row_targets) == 1:
                 # Only targeting a Step
                     parameter_data["parameters"][series["step_name"]][series["value_name"]] = series["value"]
                 elif "process" in row_targets:
                     parameter_data["process"]["parameters"][series["process_name"]][series["step_name"]][series["value_name"]] = series["value"]
                 elif "analysis" in row_targets:
                     parameter_data["process"]["analysis"]["parameters"][series["analysis_name"]][series["step_name"]][series["value_name"]] = series["value"]
                 elif "result" in row_targets:
                     parameter_data["process"]["analysis"]["result"]["parameters"][series["result_uuid"]][series["step_name"]][series["value_name"]] = series["value"]
        # Loop through these models, fetch the relevant objects in bulk, then fetch individually and query the parameters
        parameter_list = [ (Step, parameter_data["parameters"]),
                           (Process, parameter_data["process"]["parameters"]),
                           (Analysis, parameter_data["process"]["analysis"]["parameters"]),
                           (Result, parameter_data["process"]["analysis"]["result"]["parameters"])]
        print("Validating data")
        for model, obj_list in parameter_list:
            instances = model.objects.filter(**{model.id_field + "__in": [x for x in obj_list.keys() if x!="parameters"]}).prefetch_related("values")
            for Obj in obj_list:
                obj = instances.filter(**{model.id_field:Obj})
                db_params = obj.get().get_parameters()
                queryset_list = [obj]
                if model.base_name == "step":
                    in_params = obj_list[Obj]
                    diff_params = {x: y for x, y in in_params.items() if (x not in db_params) or ((x in db_params) and (str(db_params[x])!=str(in_params[x])))}
                    for value_name, value in diff_params.items():
                        cls.create_value(value_name, "parameter", value, linked_to=queryset_list)
                else:
                    for step in obj_list[Obj]:
                        step_obj = Step.objects.filter(name=step)
                        in_params = obj_list[Obj][step]
                        queryset_list = [obj, step_obj]
                        if model.base_name == "result":
                            step_params = db_params
                        else:
                            step_params = db_params[step]
                        diff_params = {x: y for x, y in in_params.items() if (x not in step_params) or ((x in step_params) and (str(step_params[x])!=str(in_params[x])))}
                        for value_name, value in diff_params.items():
                            cls.create_value(value_name, "parameter", value, linked_to=queryset_list)

    @classmethod
    def add_measures(cls, input_table, database_table, log=None):
        print("Adding measures")
        # MEASURES
        # Heuristics:
        # - All Measures must be linked to a Result, as a measure without a Result is metadata that has no provenance
        # Build up kwargs for all items in the table
        _id_fields = id_fields()
        for idx, series in input_table.iterrows():
            series = series.dropna()
            value_name = series["value_name"]
            if sum([x in series for x in Result.get_id_fields()]) == 0:
                if log is not None:
                    log.error("Line %d: Measure %s requires a Result", idx, value_name)
                continue
            value = series["value"]
            targets = [series[x] for x in series.dropna().index if x.startswith("value_target")]
            target_ids = series[[x for x in series.index if (x.split("_")[0] in targets) and (x in _id_fields)]]
            links = defaultdict(list)
            for field, target_id in target_ids.items():
                links[field].append(target_id)
            linked_to = [Obj.get_queryset(links) for Obj in object_list]
            if cls._in_table(database_table, value_name, "measure", linked_to=linked_to):
                if not cls._in_table(database_table, value_name, "measure", value, linked_to):
                    log.error("Line %d: Value mismatch, did not overwrite Value\
                               Name %s Type %s value %s, linked to %s" % (idx, value_name, "measure", str(value), str(linked_to)))
            else:
                cls.create_value(value_name, "measure", value, linked_to)


    @classmethod
    def add_metadata(cls, input_table, database_table, log=None):
        print("Adding metadata")
        # METADATA
        # Heuristics:
        # - Metadata can be attached to basically anything for any reason
        # - Grab all Objects referenced, then from theoretically smallest to largest table, search in those Objects for those Metadata linked to it
        # - If not found, make it and remove it from the proposed list
        _id_fields = id_fields()
        for idx, series in input_table.iterrows():
            series = series.dropna()
            value_name = series["value_name"]
            value = series["value"]
            targets = [series[x] for x in series.index if x.startswith("value_target")]
            target_ids = series[[x for x in series.index if (x.split("_")[0] in targets) and (x in _id_fields)]]
            links = defaultdict(list)
            for field, target_id in target_ids.items():
                links[field].append(target_id)
            linked_to = [Obj.get_queryset(links) for Obj in object_list]
            if cls._in_table(database_table, value_name, "metadata", linked_to=linked_to):
                if not cls._in_table(database_table, value_name, "metadata", value, linked_to):
                    log.error("Line %d: Value mismatch, did not overwrite Value\
                               Name %s Type %s value %s, linked to %s" % (idx, value_name, "metadata", str(value), str(linked_to)))
            else:
                cls.create_value(value_name, "metadata", value, linked_to)

    @classmethod
    def _table_queryset(cls, table):
        queryset_list = []
        for Obj in object_list:
            fields = {}
            for field in Obj.get_value_fields() + Obj.get_id_fields():
                if field in table.columns.str.split(".").str.get(0):
                    unique_ids = table[table.columns[table.columns.str.startswith(field)]].melt().dropna()["value"].unique()
                    fields[field] = unique_ids.tolist()
            qs = Obj.get_queryset(fields)
            if qs.exists():
                queryset_list.append(qs)
        return queryset_list

    @classmethod
    def add_values(cls, table, log=None):
        print("Grabbing queryset from table")
        table_objects = cls._table_queryset(table)
        print("Grabbing all values from querysets")
        all_vals = Value.objects.none()
        for val_qs in [Value.objects.filter(**{obj_qs.model.plural_name+"__in": obj_qs}) for obj_qs in table_objects]:
            all_vals = all_vals | val_qs
        print("Aggregating all info")
        database_value_table = Value.queryset_to_table(all_vals, indexes="pk")
        print("Params")
        cls.add_parameters(table[table["value_type"]=="parameter"], database_value_table, log)
        print("Measures")
        cls.add_measures(table[table["value_type"]=="measure"], database_value_table, log)
        print("Metadata")
        cls.add_metadata(table[table["value_type"]=="metadata"], database_value_table, log)

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
                        values = values | obj.get_values(name=name, value=value_type)
        return values

    def upstream_values(self, name, value_type, linked_to, only=False, include_self=True):
        # Search strictly upstream objects of the links of this one
        pass

    @classmethod
    def queryset_to_table(cls, value_queryset, indexes=None, additional_values=[]):
        values = ["pk", "name"]
        values.extend([Obj.plural_name + "__" + Obj.id_field for Obj in object_list])
        values.extend([Val.type_name + "__value" for Val in value_list])
        values.extend(additional_values)
        value_queryset = value_queryset.prefetch_related(*[Obj.plural_name for Obj in object_list])
        value_queryset = value_queryset.values(*values)
        table = pd.DataFrame.from_records(value_queryset)
        values.pop(values.index("pk"))
        values.pop(values.index("name"))
        values = [value for value in values if value in table.columns]
        if len(values) == 0:
            return pd.DataFrame()
        if isinstance(indexes, str):
            if indexes in values:
                values.pop(values.index(indexes))
        elif hasattr(indexes, '__iter__'):
            for ind in indexes:
                if ind in values:
                    values.pop(values.index(ind))
#            table = table.pivot(index=indexes, columns="name", values=values)
        # This is what happens when there are multiple values for a given key
        # and it must aggregate them
        # This is slower, but reserving the x.dropna() for when we know
        # there's more than one value in there speeds it up
        def agg_fun(x):
            if len(x) == 1:
                return set([str(x.values[0])]) if pd.notnull(x.values[0]) else np.nan
            elif len(x) > 1:
                x=x.dropna()
                if len(x) >=1:
                    return set([str(y) for y in x.dropna().values])
                else:
                    return np.nan
            else:
                return np.nan
        table = table.pivot_table(index=indexes, columns=["name"], values=values,
                                  aggfunc=agg_fun)
        return table.dropna(axis=1, how='all')

    @classmethod
    def _in_table(cls, table, value_name, value_type, value=None, linked_to=None):
        #Convert the queryset list into something easier to compare in a Pandas table
        linked_two = []
        for qs in linked_to:
            model = qs.model
            for obj in qs:
                linked_two.append((model, str(getattr(obj, model.id_field))))
        linked_to = linked_two
        # linked_to = [(Model, id), ...]
        # If value is not None, we will check to make sure that value is identical
        if value_name not in table.columns.get_level_values("name"):
            return False
        vname_table = table.xs(value_name, level="name", axis=1).dropna(axis=0, how='all')
        fields = defaultdict(set)
        for model, obj_id in linked_to:
            field = model.plural_name + "__" + model.id_field
            fields[field].add(obj_id)
        for field in fields:
            vname_table = vname_table.where(vname_table[field] == fields[field]).dropna(axis=0, how='all')
            if vname_table.empty:
                return False
        for Obj in object_list:
            field = Obj.plural_name + "__" + Obj.id_field
            if (field in vname_table) and (field not in fields):
                vname_table = vname_table.where(pd.isna(vname_table[field])).dropna(axis=0, how='all')
                if vname_table.empty:
                    return False
        if value is None:
            return True
        else:
            value_fields = vname_table.columns[vname_table.columns.str.contains("__value")]
            if len(value_fields) > 1:
                raise ValueError("Two value types found in database for %s %s" % (value_type, value_name))
            elif len(value_fields) == 0:
                raise ValueError("No value column for %s %s" % (value_type, value_name))
            else:
                value_field = value_fields[0]
            vname_table = vname_table.where(vname_table[value_field].apply(lambda x: (value in x) or (str(value) in x)))
            vname_table = vname_table.dropna(axis=1, how='all').dropna(axis=0, how='all')
            if vname_table.empty:
                return False
            if vname_table.shape[0] > 1:
                raise ValueError("Found two Values with the same signature: Type: %s, Name: %s, Value: %s, Links: %s" % (value_type, value_name, value, str(linked_to)))
            return True

    @classmethod
    def relate_value_sets(cls, A, B):
        # Link all Values in A to all Values in B, if possible
        pass

    @classmethod
    def disambiguate(cls, name, value_type=None, linked_to=None, only=False, return_queryset=False):
        #Like most functions, try to kick out as soon as we know there's an ambiguity we can resolve
        qs = Value.objects.filter(name=name)
        if value_type is not None:
            qs = qs.filter(value=value_type)
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
            if found_types[0].model_class() == None:
                raise ValueError("Retrieved a null model class for value name %s type %s" % (value_name, value_type))
            return found_types[0].model_class()
        elif value != None:
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
                            SearchVector('type', weight='B'))
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
    cast_function = lambda x: Result.objects.get(uuid=str(x))
    value = models.ForeignKey('Result', on_delete=models.CASCADE)
    val_obj = GenericRelation(Value, related_query_name=type_name)

    def __str__(self):
        return value.name + ": " + value.type



object_list = [Investigation, Sample, Feature, Step, Process, \
               Analysis, Result]
value_list = [StrVal, IntVal, FloatVal, DatetimeVal, ResultVal]
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

def reference_proxies():
    proxies = defaultdict(list)
    for field, source_model, ref_model in reference_fields():
        if ref_model.base_name not in ["value", "category", "file"]:
            for proxy in ref_model.get_id_fields():
                proxies[field].append(proxy)
    return proxies

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

class LogFile(models.Model):
    base_name = "log"
    plural_name = "logs"

    # Define log types here
    TYPE_CHOICES = (
            ('U', 'Upload Log'),
            ('F', "Upload File Log"),
            ('A', "User Action Log")
    )

    DEFAULT_LOG_FILENAMES = {'U': "all_uploads.log",
                             'F': "upload_%d.log",
                             'A': "user_actions.log"}

    log = models.FileField(upload_to='logs', blank=True, null=True)
    # Text description of the log type
    type = models.CharField(max_length=1, choices=TYPE_CHOICES)
    # When the log was written
    date_created = models.DateTimeField(auto_now_add=True)
    # Last update to it
    last_updated = models.DateTimeField(auto_now=True)

    def get_log_path(self):
        if not self.pk:
            raise ValueError("LogFile instance must be saved before a log path can be retrieved")
        if self.type=='F':
            if not self.file:
                raise ValueError("Uninitialized Upload File Log. Must be set to\
                        a File object's logfile field and saved before a logger\
                        can be retrieved")
            # Should have a File pointed at it, so
            fileobj = self.file
            pk = fileobj.pk
            return settings.LOG_ROOT + "/uploads/" + self.DEFAULT_LOG_FILENAMES['F'] % (pk,)
        else:
            return settings.LOG_ROOT + "/" + self.DEFAULT_LOG_FILENAMES[self.type]

    def get_logger(self):
        # Return the Logger instance for this logfile, which will push updates
        # to the appropriate File
        #NOTE: Loggers are not garbage collected, so there's always a chance
        # that we'll stumble back on an old logger if we aren't careful with
        # the uniqueness of the names
        if not self.pk:
            raise ValueError("LogFile instance must be saved before a logger can be retrieved")

        # If this object doesn't have a log file created for it yet, do it now
        # This should be fine here since it is only needed once a logger is called
        # and begins pushing to it
        if not self.log:
            print("No log, making log file")
            path = self.get_log_path()
            print(path)
            logfile = files.File(open(path, 'w+b'))
            print("Opened logfile at that path and made it into a files.File")
            self.log.save(path, logfile)

        if self.type == 'F':
            # Should have a File pointed at it, or get_log_path would've errored and we'd have no self.log
            fileobj = self.file
            pk = fileobj.pk
            lgr = logging.getLogger("quorem.uploads.%d" % (pk,))
            if not lgr.hasHandlers():
                lgr.addHandler(logging.StreamHandler(stream=self.log))
            #TODO: Add a formatter, set levels properly
            #TODO: Define quorem.uploads and its configuration
        elif self.type == 'U':
            lgr = logging.getLogger("quorem.uploads")
            if not lgr.hasHandlers():
                lgr.addHandler(logging.StreamHandler(stream=self.log))
        return lgr

    def tail(self, n=10):
        # Get the last n lines of this log
        # This function needs to open up and scrape self.log
        pass

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
    logfile = models.OneToOneField(LogFile, on_delete=models.CASCADE, related_name="file")
    upload_status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    upload_type = models.CharField(max_length=1, choices=TYPE_CHOICES)
    #Should upload files be indexed by the search??
    #search_vector = SearchVectorField(null=True)

    def __str__(self):
        return "UserProfile: {0}, UploadFile: {1}".format(self.userprofile, self.upload_file)

    def save(self, *args, **kwargs):
        self.upload_status = 'P'
        lf = LogFile(type='F')
        lf.save()
        self.logfile = lf
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
