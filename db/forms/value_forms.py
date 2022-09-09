# ----------------------------------------------------------------------------
# path: quorem/db/forms/value_forms.py
# authors: Mike Hall
# modified: 2022-09-08
# description: This file contains all Value related forms
# ----------------------------------------------------------------------------

import django_filters

from ..models import (
    Value,
)

from django.forms import ModelForm

class ValueDetailForm(ModelForm):
    class Meta:
        model = Value
        exclude = ['search_vector']

class ValueFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Value Name Contains", field_name="signature__name")
    class Meta:
        model = Value
        exclude = ['search_vector', 'polymorphic_ctype']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
