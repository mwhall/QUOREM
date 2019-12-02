from django.db import models
from django.apps import apps

#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.aggregates import StringAgg

from db.models.object import Object

class Feature(Object):
    base_name = "feature"
    plural_name = "features"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ff5497'}

    description = "A Feature represents something that is being tracked across Samples, such as a taxonomic group, a functional gene, or a molecule"

    name = models.CharField(max_length=255, verbose_name="Name")
    samples = models.ManyToManyField('Sample', related_name='features', blank=True)

    annotations = models.ManyToManyField('Value', related_name='+', blank=True)
    values = models.ManyToManyField('Value', related_name="features", blank=True)

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector = (SearchVector('name', weight= 'A') +
                             SearchVector(StringAgg('annotations__str', delimiter=' '), weight='B'))
        )

    def related_samples(self, upstream=False):
        #SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_results(self, upstream=False):
        # SQL Depth: 2
        results = self.results.all()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results
