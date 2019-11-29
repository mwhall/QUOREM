from django.db import models
from django.apps import apps

#for searching
from django.contrib.postgres.search import SearchVector

from db.models.object import Object

class Step(Object):
    base_name = "step"
    plural_name = "steps"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#d4f5ff'}

    has_upstream = True

    description = "A Step is an arbitrarily-defined set of instructions that belongs to a Process and may emit a Result"

    name = models.CharField(max_length=255)
    processes = models.ManyToManyField('Process', related_name='steps', blank=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)
    values = models.ManyToManyField('Value', related_name='steps', blank=True)

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
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
        samples = apps.get_model("db", "Sample").objects.filter(source_step__pk=self.pk)
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_processes(self, upstream=False):
        processes = self.processes.all()
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_analyses(self):
        # SQL Depth: 2
        return apps.get_model("db", "Analysis").objects.filter(extra_steps__pk=self.pk,
                                       process__in=self.related_processes()).distinct()

    def related_results(self, upstream=False):
        # Results ejected from this step
        results = apps.get_model("db", "Result").objects.filter(source_step__pk=self.pk)
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results
