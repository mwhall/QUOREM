# ----------------------------------------------------------------------------
# path: quorem/db/forms/step_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all step related forms
# ----------------------------------------------------------------------------

import django_filters

from ..models import (
    Step,
)

from django.forms import ModelForm

class StepDetailForm(ModelForm):
    class Meta:
        model = Step
        exclude = ['search_vector', 'values']

class StepFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    class Meta:
        model = Step
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
