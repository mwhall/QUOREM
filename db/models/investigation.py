from django import forms
from django.db import models
from django.apps import apps
from django.utils.html import mark_safe, format_html
#for searching
from django.contrib.postgres.search import SearchVector

from collections import OrderedDict

from .object import Object

class Investigation(Object):
    base_name = "investigation"
    plural_name = "investigations"

    description = "An Investigation represents a group of Samples"

    grid_fields = ["name", "samples"]
    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#aeaee8'}

    name = models.CharField(max_length=255, unique=True)
    values = models.ManyToManyField('Value', related_name="investigations", blank=True)

    def related_samples(self, upstream=False):
        # SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())

    def html_samples(self):
        sample_count = self.samples.count()
        accordions = {'samples': {'heading': format_html('Show Samples ({})', str(sample_count))}}
        content = ""
        for sample in self.samples.all():
            content += format_html("{}<BR/>", mark_safe(str(sample)))
        accordions['samples']['content'] = content
        return self._make_accordion("samples", accordions)

    @classmethod
    def get_display_form(cls):
        from django_jinja_knockout.widgets import DisplayText
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            sample_accordion = forms.CharField(widget=DisplayText(), label="Samples")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['sample_accordion'] = mark_safe(kwargs['instance'].html_samples())
                super().__init__(*args, **kwargs)
                self.fields.move_to_end("value_accordion")
        return DisplayForm

    @classmethod
    def get_crud_form(cls):
        CrudForm = super().get_crud_form()
        class CustomMMChoiceField(forms.ModelMultipleChoiceField):
            def label_from_instance(self, obj):
                count = obj.results.values("samples").distinct().count()
                return "%s (%d %s)" % (obj.name, count, "Sample" if (count==1) else "Samples")
        class InvestigationCrudForm(CrudForm):
            samples = forms.ModelMultipleChoiceField(queryset=apps.get_model("db.Sample").objects.all(),
                                                   label="Add/Remove Samples Individually",
                                                   required=False)
            analyses = CustomMMChoiceField(queryset=apps.get_model("db.Analysis").objects.all(), 
                                           label="Add Samples from Analyses",
                                           required=False)
            def __init__(self, *args, **kwargs):
                if 'instance' in kwargs:
                    kwargs['initial'] = {'samples': [x.pk for x in kwargs['instance'].samples.all()]}
                super().__init__(*args, **kwargs)
            def save(self, commit=True):
                instance = super().save(commit=False)
                instance.samples.set(self.cleaned_data['samples'])
                for analysis in self.cleaned_data['analyses']:
                    instance.samples.add(*analysis.results.filter(samples__isnull=False).values_list("samples__pk", flat=True))
                if commit:
                    instance.save()
                return instance 

            class Meta:
                model = cls
                exclude = ['search_vector', 'values']

        return InvestigationCrudForm

