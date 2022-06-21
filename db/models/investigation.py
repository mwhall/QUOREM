from django import forms
from django.db import models
from django.apps import apps
from django.utils.html import mark_safe, format_html
#for searching
from django.contrib.postgres.search import SearchVector

from collections import OrderedDict

from .object import Object

class Investigation(Object):
    base_name = "investigation"
    plural_name = "investigations"

    description = "An Investigation represents a group of Samples"

    grid_fields = ["name", "samples"]
    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#aeaee8'}

    name = models.CharField(max_length=255, unique=True)
    values = models.ManyToManyField('Value', related_name="investigations", blank=True)

    def related_samples(self, upstream=False):
        # SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())

    def html_samples(self):
        sample_count = self.samples.count()
        accordions = {'samples': {'heading': format_html('Show Samples ({})', str(sample_count))}}
        content = ""
        for sample in self.samples.all():
            content += format_html("{}<BR/>", mark_safe(str(sample)))
        accordions['samples']['content'] = content
        return self._make_accordion("samples", accordions)

