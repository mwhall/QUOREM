from collections import defaultdict
from django.db import models

#for searching
from django.contrib.postgres.search import SearchVector

from db.models.object import Object

class Analysis(Object):
    base_name = "analysis"
    plural_name = "analyses"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffb37f'}

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
