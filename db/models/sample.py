from django.db import models

#for searching
from django.contrib.postgres.search import SearchVector

from .object import Object

class Sample(Object):
    base_name = "sample"
    plural_name = "samples"

    has_upstream = True

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#aee8ae'}

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

