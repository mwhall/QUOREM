from django.db import models
from django.apps import apps

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
