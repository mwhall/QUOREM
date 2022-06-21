# ----------------------------------------------------------------------------
# path: quorem/db/forms/investigation_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all investigation related forms
# ----------------------------------------------------------------------------

import django_filters

from collections import OrderedDict

from ..models import Investigation

from django.utils.html import mark_safe
from django import forms
from django.forms import ModelForm

class InvestigationDetailForm(ModelForm):
    sample_accordion = forms.CharField(label="Samples")
    node = None #Cheating way to override parent's Node and hide it
    class Meta:
        model = Investigation
        exclude = ['search_vector', 'values']
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            kwargs['initial'] = OrderedDict()
            kwargs['initial']['sample_accordion'] = mark_safe(kwargs['instance'].html_samples())
        super().__init__(*args, **kwargs)
        self.fields.move_to_end("value_accordion")

class InvestigationCreateForm(ModelForm):
    class Meta:
        model = Investigation
        fields = ['name']
    def __init__(self, *args, **kwargs):
        super(InvestigationCreateForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'

class InvestigationFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    class Meta:
        model = Investigation
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
