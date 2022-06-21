# ----------------------------------------------------------------------------
# path: quorem/db/forms/process_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all process related forms
# ----------------------------------------------------------------------------

import django_filters

from collections import OrderedDict

from django import forms
from django.utils.html import mark_safe
from django.db import models
from ..models import (
    Investigation,
    Process, Step,
)

from django.forms import ModelForm

from dal import autocomplete

class ProcessDetailForm(ModelForm):
    step_accordion = forms.CharField(label="Steps")
    node = None #Cheating way to override parent's Node and hide it
    class Meta:
        model = Process
        exclude = ['search_vector', 'values', 'all_upstream']
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            kwargs['initial'] = OrderedDict()
            kwargs['initial']['step_accordion'] = mark_safe(kwargs['instance'].html_steps())
        super().__init__(*args, **kwargs)
        self.fields = OrderedDict(self.fields)
        self.fields.move_to_end("value_accordion")
        self.fields.move_to_end("graph")

class ProcessCreateForm(ModelForm):
    class Meta:
        model = Process
        fields = ['name']
    def __init__(self, *args, **kwargs):
        super(ProcessCreateForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'

class ProcessFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    class Meta:
        model = Process
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
