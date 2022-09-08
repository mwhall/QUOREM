from django.db import models
from django.apps import apps
from django import forms
from django.utils.html import mark_safe, format_html

from django.views.generic.detail import DetailView

#for searching
from django.contrib.postgres.search import SearchVector
from collections import OrderedDict
from .object import Object

from django_pandas.managers import DataFrameManager

class Sample(Object):
    base_name = "sample"
    plural_name = "samples"

    has_upstream = True

    description = "A Sample generally represents matter that was taken from a location at some date and time, or derived from something that was"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#aee8ae'}
    grid_fields = ["name", "source_step", "investigations"]

    name = models.CharField(max_length=255,unique=True,db_index=True)
    investigations = models.ManyToManyField('Investigation', related_name='samples', blank=True)  # fk 2
    source_step = models.ForeignKey('Step', related_name='samples', on_delete=models.CASCADE, blank=True, null=True)
    features = models.ManyToManyField('Feature', related_name='samples', blank=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    # A cache of all of the upstream Samples up the chain
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="samples", blank=True)

    @classmethod
    def update_search_vector(cls):
        sv = (SearchVector('name', weight='A') +
                        SearchVector('values__signature__name', weight='B') +
                        SearchVector('values__signature__data', weight='C')

        )
        cls.objects.update(
            search_vector= sv
        )

#        refresh_automated_report("sample", pk=self.pk)

    def related_investigations(self):
        return self.investigations.all()

    def related_features(self):
        return self.features.all()

    def related_steps(self, upstream=False):
        steps = apps.get_model("db", "Step").objects.filter(pk=self.source_step.pk)
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_results(self, upstream=False):
        # SQL Depth: 1
        results = self.results.all()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results.distinct()

    def html_features(self):
        feature_count = self.features.count()
        accordions = {'features': {'heading': format_html('Show Features ({})', str(feature_count))}}
        content = ""
        for feature in self.features.all():
            content += format_html("{}<BR/>", mark_safe(str(feature)))
        accordions['features']['content'] = content
        return self._make_accordion("features", accordions)

