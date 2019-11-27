from django.db import models
from django.apps import apps

#for searching
from django.contrib.postgres.search import SearchVector

from .object import Object

class Investigation(Object):
    base_name = "investigation"
    plural_name = "investigations"

    name = models.CharField(max_length=255, unique=True)

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#aeaee8'}

    values = models.ManyToManyField('Value', related_name="investigations", blank=True)

    @classmethod
    def update_search_vector(cls):
        sv =( SearchVector('name', weight='A'))
        cls.objects.update(search_vector = sv)
#        refresh_automated_report("investigation")
#        refresh_automated_report("investigation", pk=self.pk)

    def related_samples(self, upstream=False):
        # SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
