from collections import defaultdict

from django.db import models
#for searching
from django.contrib.postgres.search import SearchVector

from db.models.object import Object

class Process(Object):
    base_name = "process"
    plural_name = "processes"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffd4d4'}

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
