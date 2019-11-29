from collections import defaultdict

from django.db import models
from django.apps import apps

#for searching
from django.contrib.postgres.search import SearchVector

from db.models.object import Object

class Process(Object):
    base_name = "process"
    plural_name = "processes"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffd4d4'}

    description = "A set of Steps run with a typical series of Parameters"

    has_upstream = True

    name = models.CharField(max_length=255, unique=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name="downstream", blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="processes", blank=True)

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector = (SearchVector('name', weight='A')
        ))

    def related_steps(self, upstream=False):
        steps = self.steps.all()
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_analyses(self):
        return self.analyses.all()
