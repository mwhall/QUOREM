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

from quorem.wiki import refresh_automated_report

User = get_user_model()

class Object(models.Model):
    base_name = "object"
    plural_name = "objects"
    has_upstream = False
    search_set = None

    search_vector = SearchVectorField(null=True)

    class Meta:
        abstract = True
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.id_column = base_name + "_id"
        if self.has_upstream:
            self.upstream_column = "upstream_" + base_name
        self.category_column = base_name + "_category"
        self.search_set = self.__class__.objects.filter(pk=self.pk)

    @combomethod
    def with_values(receiver, name, value_type=None, linked_to=None, search_set=None, upstream=False, only=False):
        linkable_objects = ["samples", "features", "analyses", "steps", "processes",\
                            "results", "investigations"]
        if search_set is None:
            search_set = receiver._meta.model.objects.all()
        search_set = search_set.prefetch_related("values")
        if self.has_upstream & upstream:
            search_set = search_set.prefetch_related("all_upstream")
            upstream_set = receiver._meta.model.objects.filter(pk__in=search_set.values("all_upstream__pk").distinct())
            search_set = search_set.union(upstream_set).distinct()
        kwargs = {"values__name": name, "pk__in": search_set}
        if value_type is not None:
            kwargs["values__value_type"] = value_type
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
        return receiver.with_values(name, "metadata", linked_to, 
                                    search_set, upstream, only)

    @combomethod
    def with_measure(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_values(name, "measure", linked_to, 
                                    search_set, upstream, only)

    @combomethod
    def with_parameter(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_values(name, "parameter", linked_to, 
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
        return self.values.filter(name=name, value_type=value_type)

    def get_upstream_values(self, name, value_type):
        if not self.has_upstream:
            return Value.objects.none()
        return Value.objects.filter(pk__in=self.all_upstream.values("values__pk"))

class Investigation(Object):
    base_name = "investigation"
    plural_name = "investigations"

    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255)
    description = models.TextField()

    values = models.ManyToManyField('Value', related_name="investigations", blank=True)
    categories = models.ManyToManyField('Category', related_name='investigations', blank=True)
    #Stuff for searching
    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('investigation_detail', kwargs={'investigation_id': self.pk})}), self.name))

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

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('feature_detail', kwargs={'feature_id': self.pk})}), self.name))

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
    """
    Uniquely identify a single sample (i.e., a physical sample taken at some single time and place)
    """
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

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('sample_detail', kwargs={'sample_id': self.pk})}), self.name))

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

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('process_detail', kwargs={'process_id': self.pk})}), self.name))

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

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('step_detail', kwargs={'step_id': self.pk})}), self.name))

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

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('analysis_detail', kwargs={'analysis_id': self.pk})}), self.name))

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

    has_upstream = True

    list_display = ('source', 'type', 'source_step', 'processes', 'samples', 'values', 'uuid')
    uuid = models.UUIDField(unique=True) #For QIIME2 results, this is the artifact UUID
    input_file = models.ForeignKey('UploadInputFile', on_delete=models.CASCADE, verbose_name="Result File Name", blank=True, null=True)
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

    def get_detail_link(self, label='uuid'):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('result_detail', kwargs={'result_id': self.pk})}), str(getattr(self, label))))

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
    PARAMETER = 'parameter'
    METADATA = 'metadata'
    MEASURE = 'measure'
    VALUE_TYPES = (
            (PARAMETER, 'Parameter'),
            (METADATA, 'Metadata'),
            (MEASURE, 'Measure'))
    name = models.CharField(max_length=512)
    value_type = models.CharField(max_length=9, choices=VALUE_TYPES)
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

    def get_links(self):
        linked_to = [ x for x in self.linkable_objects if getattr(self, x).exists() ]
        self_link_ids = {}
        for field in linked_to:
            self_link_ids[field] = []
            for obj in getattr(self, field).all():
                if field == "results":
                    _id = str(obj.uuid)
                else:
                    _id = str(obj.name)
                self_link_ids[field].append(_id)
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
                related_with_target = model.with_values(name, value_type,
                                         linked_to, queryset, upstream, only)
                if related_with_target != False:
                    for obj in related_with_target:
                        values = values | obj.get_values(name=name, value_type=value_type)
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
        linkable_objects = ["samples", "features", "analyses", "steps", "processes",\
                            "results", "investigations"]
        #Like most functions, try to kick out as soon as we know there's an ambiguity we can resolve
        qs = Value.objects.filter(name=name)
        if value_type is not None:
            qs = qs.filter(value_type=value_type)
        qs = qs.prefetch_related("samples","features","analyses",
                                 "investigations","steps","processes","results")
        if linked_to is not None:
            if isinstance(linked_to, list):
                kwargs = {}
                for link in linked_to:
                    kwargs[link + "__isnull"] = False
                if only:
                    for obj in linkable_objects:
                        if obj + "__isnull" not in kwargs:
                            kwargs[obj + "__isnull"] = True
                qs = qs.filter(**kwargs)
            else:
                 kwargs = {linked_to + "__isnull": False}
                 if only:
                     for obj in linkable_objects:
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
        qs = qs.values("value_type","samples_count","features_count",
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
                    signature_dict[signature["value_type"]].add(tuple(link_list))
            return signature_dict

    @classmethod
    def update_search_vector(self):
        Value.objects.update(
            search_vector= (SearchVector('name', weight='A') +
#                            SearchVector('', weight='B') +
                            SearchVector('value_type', weight='B'))
        )


class StrVal(models.Model):
    value = models.TextField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="str")

class IntVal(models.Model):
    value = models.IntegerField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="int")

class FloatVal(models.Model):
    value = models.FloatField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="float")

class DatetimeVal(models.Model):
    value = models.DateTimeField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="date")

#This is if the input parameter is another result, ie. another artifact searched by UUID
class ResultVal(models.Model):
    value = models.ForeignKey('Result', on_delete=models.CASCADE)
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="uuid")
    def __str__(self):
        return value.name + ": " + value.type



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


class UploadInputFile(models.Model):
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
        #return reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': self.pk})

class ErrorMessage(models.Model):
    """
    Store error messages for file uploads.
    """
    uploadinputfile = models.ForeignKey(UploadInputFile, on_delete=models.CASCADE, verbose_name='Uploaded File')
    error_message = models.CharField(max_length = 1000, null=True) #???? Maybe store as a textfile????


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
