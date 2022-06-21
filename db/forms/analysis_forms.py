# ----------------------------------------------------------------------------
# path: quorem/db/forms/analysis_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all analysis related forms
# ----------------------------------------------------------------------------

import django_filters

from collections import OrderedDict

from django import forms
from django.utils.html import mark_safe
from django.db import models
from ..models import (
    Process, 
    Analysis,
    Result,
)
from django.forms import ModelForm

from dal import autocomplete

class AnalysisDetailForm(ModelForm):
    result_accordion = forms.CharField(label="Results")
    node = None #Cheating way to override parent's Node and hide it
    class Meta:
        model = Analysis
        exclude = ['search_vector', 'values']
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            kwargs['initial'] = OrderedDict()
            kwargs['initial']['result_accordion'] = mark_safe(kwargs['instance'].html_results())
        super().__init__(*args, **kwargs)
        self.fields.move_to_end("value_accordion")

class AnalysisSelectForm(forms.Form):
    analysis = forms.ModelChoiceField(queryset=Analysis.objects.all(),
                                      label="Analysis",
                                      widget=autocomplete.ModelSelect2(url='object-analysis-autocomplete',
                                                                       attrs={"data-allow-clear": "true", 
                                                                              "style": "flex-grow: 1", 
                                                                              "data-html": True}))

class AnalysisCreateForm(ModelForm):
    class Meta:
        model = Analysis
        fields = ['name','process']
        widgets = {'process': autocomplete.ModelSelect2(url='object-process-autocomplete',
                                                        attrs={"data-allow-clear": "true", "style": "flex-grow: 1", "data-html": True})}
    def __init__(self, *args, **kwargs):
        super(AnalysisCreateForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'

class AnalysisFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    class Meta:
        model = Analysis
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
