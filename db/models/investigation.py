from django.db import models

#for searching
from django.contrib.postgres.search import SearchVector

from .object import Object
from .sample import Sample

class Investigation(Object):
    base_name = "investigation"
    plural_name = "investigations"

    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255)
    description = models.TextField()

    values = models.ManyToManyField('Value', related_name="investigations", blank=True)
    categories = models.ManyToManyField('Category', related_name='investigations', blank=True)

    @classmethod
    def update_search_vector(self):
        sv =( SearchVector('name', weight='A') +
             SearchVector('description', weight='B') +
             SearchVector('institution', weight='C') )
        Investigation.objects.update(search_vector = sv)
#        refresh_automated_report("investigation")
#        refresh_automated_report("investigation", pk=self.pk)

    def related_samples(self, upstream=False):
        # SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | Sample.objects.filter(pk__in=self.samples.values("all_upstream").distinct())
