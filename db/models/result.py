from django.db import models
from django.forms.utils import flatatt
from django.utils.html import mark_safe, format_html
from django.urls import reverse
#for searching
from django.contrib.postgres.search import SearchVector

from django.apps import apps

from db.models.object import Object

class Result(Object):
    """
    Some kind of result from an analysis
    """
    base_name = "result"
    plural_name = "results"
    id_field = "uuid"
    has_upstream = True

    list_display = ('source', 'type', 'source_step', 'processes', 'samples', 'values', 'uuid')
    uuid = models.UUIDField(unique=True) #For QIIME2 results, this is the artifact UUID
    file = models.ForeignKey('File', on_delete=models.CASCADE, verbose_name="Result File Name", blank=True, null=True)
    source = models.CharField(max_length=255, verbose_name="Source Software/Instrument", blank=True, null=True)
    type = models.CharField(max_length=255, verbose_name="Result Type", blank=True, null=True)
    analysis = models.ForeignKey('Analysis', related_name='results', on_delete=models.CASCADE)
    # This process result is from this step
    source_step = models.ForeignKey('Step', on_delete=models.CASCADE, verbose_name="Source Step", blank=True, null=True)
    # Samples that this thing is the result for
    samples = models.ManyToManyField('Sample', related_name='results', verbose_name="Samples", blank=True)
    features = models.ManyToManyField('Feature', related_name='results', verbose_name="Features", blank=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)
    #from_provenance = models.BooleanField(default=False)

    values = models.ManyToManyField('Value', related_name="results", blank=True)
    categories = models.ManyToManyField('Category', related_name='results', blank=True)

    def __str__(self):
        return str(self.uuid)

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 self.type + " from " + self.source_step.name))

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector= (SearchVector('source', weight='A') +
                            SearchVector('type', weight='B') +
                            SearchVector('uuid', weight='C'))
        )

    def get_parameters(self):
        # Get the parameters for this Result, with respect to its source step
        parameters = {}
        for queryset in [self.source_step.values.filter(results=self),
                         self.analysis.process.values,
                         self.analysis.values,
                         self.values]:
            for value in queryset.filter(steps=self.source_step, type="parameter"):
                parameters[value.name] = value.content_object.value
        return parameters

    def related_samples(self, upstream=False):
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_features(self):
        return self.features.all()

    def related_steps(self, upstream=False):
        if not self.source_step:
            return apps.get_model("db", "Step").objects.none()
        steps = apps.get_model("db", "Step").objects.filter(pk=self.source_step.pk)
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_processes(self, upstream=False):
        processes = apps.get_model("db", "Process").objects.filter(pk=self.analysis.process.pk)
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_analyses(self):
        return apps.get_model("db", "Analysis").objects.filter(pk=self.analysis.pk)
