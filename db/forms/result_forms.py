# ----------------------------------------------------------------------------
# path: quorem/db/forms/result_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all result related forms
# ----------------------------------------------------------------------------

import django_filters
from dal import autocomplete

from collections import OrderedDict

from django import forms
from django.utils.html import mark_safe
from django.urls import reverse
from django.db import models
from ..models import (
    Analysis,
    Result,
    Feature,
)

from django.forms import ModelForm

class ResultDetailForm(ModelForm):
    parameters = forms.CharField(label="Parameters (non-default if bold)")
    provenance = forms.CharField(max_length=4096)
    sample_accordion = forms.CharField(label="Samples")
    feature_accordion = forms.CharField(label="Features")
    node = None #Cheating way to override parent's Node and hide it
    class Meta:
        model = Result
        exclude = ['search_vector', 'values', 'all_upstream', 'features', 'samples']
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            kwargs['initial'] = OrderedDict()
            kwargs['initial']['provenance'] = mark_safe(kwargs['instance'].simple_provenance_graph().pipe().decode().replace("<svg ", "<svg class=\"img-fluid\" ").replace("\n","").replace('pt"','"'))
            kwargs['initial']['sample_accordion'] = mark_safe(kwargs['instance'].html_samples())
            kwargs['initial']['feature_accordion'] = mark_safe(kwargs['instance'].html_features())
            kwargs['initial']['parameters'] = mark_safe("<BR>".join([format_html("<b>{}: {} (set by {})</b>" if dat[1]=="result" else "{}: {} (set by {})", name, str(dat[0].data.get().get_value()), dat[1].capitalize()) for name, dat in kwargs['instance'].get_parameters()[kwargs['instance'].source_step.pk].items()]))
        super().__init__(*args, **kwargs)
        self.fields.move_to_end("value_accordion")
        self.fields.move_to_end("graph")
        self.fields["upstream"].label = "Input Results"
        self.fields["source_step"].label = "Output By Step"


class ResultFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    analysis = django_filters.ModelMultipleChoiceFilter(queryset=Analysis.objects.all(), label="Related Analysis (results must be in at least one)", to_field_name="pk", field_name="analysis",
                                                        widget=autocomplete.ModelSelect2Multiple(url='object-analysis-autocomplete',
                                                                                         attrs={"data-allow-clear": "true",
                                                                                                "style": "flex-grow: 1",
                                                                                                "class": "form-control",
                                                                                                "data-html": True}))

    class Meta:
        model = Result
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
