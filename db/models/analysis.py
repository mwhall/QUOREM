from collections import defaultdict, OrderedDict
from django import forms
from django.db import models
from django.apps import apps
from django.utils.html import mark_safe, format_html
#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.contenttypes.models import ContentType

from db.models.object import Object
from combomethod import combomethod
class Analysis(Object):
    base_name = "analysis"
    plural_name = "analyses"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffb37f'}

    description = "An Analysis represents an instantiation of a Process and its Steps, and optionally extra steps"

    # This is an instantiation/run of a Process and its Steps
    name = models.CharField(max_length=255)
    process = models.ForeignKey('Process', on_delete=models.CASCADE, related_name='analyses')
    # Run-specific parameters can go in here, but I guess Measures can too
    values = models.ManyToManyField('Value', related_name='analyses', blank=True)

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector= (SearchVector('location', weight='A'))
        )

    def get_parameters(self, steps=None, step_field="pk"):
        Parameter = apps.get_model("db.Parameter")
        if steps is None:
            steps = self.process.steps.all()
#        else:
#            steps = self.process.steps.filter(pk__in=steps)
        params = {}
        for step in steps:
            anal_params = dict([(x.signature.get().name,
                                (x, 'analysis'))
                                for x in self.values.instance_of(Parameter).filter(steps=step)])
            proc_params = self.process.get_parameters(steps=step.qs())[step.pk]
            anal_params.update(proc_params)
            if not anal_params:
                anal_params = {}
            params[getattr(step,step_field)] = anal_params
        return params

    def html_results(self):
        result_count = self.results.count()
        accordions = {'results': {'heading': format_html('Show Results ({})', str(result_count))}}
        content = ""
        for result in self.results.all():
            content += format_html("{}<BR/>", mark_safe(str(result)))
        accordions['results']['content'] = content
        return self._make_accordion("results", accordions)

    @classmethod
    def get_display_form(cls):
        from django_jinja_knockout.widgets import DisplayText
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            result_accordion = forms.CharField(widget=DisplayText(), label="Results")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['result_accordion'] = mark_safe(kwargs['instance'].html_results())
                super().__init__(*args, **kwargs)
                self.fields.move_to_end("value_accordion")
        return DisplayForm
  
    def related_samples(self, upstream=False):
        # All samples for all Results coming out of this Analysis
        samples = apps.get_model("db", "Sample").objects.filter(pk__in=self.results.values("samples").distinct())
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_steps(self, upstream=False):
        steps = self.extra_steps.all() | self.process.steps.all()
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_processes(self, upstream=False):
        results = apps.get_model("db", "Process").objects.filter(pk=self.process.pk)
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_results(self, upstream=False):
        results = self.results.all()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
