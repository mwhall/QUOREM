# ----------------------------------------------------------------------------
# path: quorem/db/forms/sample_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all sample related forms
# ----------------------------------------------------------------------------

import django_filters

from collections import OrderedDict

from django import forms
from django.db import models
from ..models import (
    Analysis,
    Sample,
    DataSignature
)

from django.utils.html import mark_safe
from django.forms import formset_factory, ModelForm

from dal import autocomplete

class SampleDetailForm(ModelForm):
     feature_accordion = forms.CharField(label="Features")
     node = None #Cheating way to override parent's Node and hide it
     graph = None
     class Meta:
         model = Sample
         exclude = ['search_vector', 'values', 'features', 'all_upstream']
     def __init__(self, *args, **kwargs):
         kwargs['initial'] = OrderedDict()
         kwargs['initial']['feature_accordion'] = mark_safe(kwargs['instance'].html_features())
         super().__init__(*args, **kwargs)
         self.fields.move_to_end("value_accordion")

class SampleFilterForm(forms.Form):
    sample_name_contains = forms.CharField(label='Sample Name Contains', 
                                           max_length=4096,
                                           widget=forms.TextInput(attrs={
                                               'class': 'form-control',
                                               'placeholder': 'Select Samples containing query (case-insensitive)'}))

#class ValueComparator(models.TextChoices):
#    EQUAL = 'EQ', _('Equal/Is (=)')
#    GREATER = 'GT', _('Greater Than (>)')
#    LESS = 'LT', _('Less Than (<)')
#    GREATER_EQUAL = 'GE', _('Greater Than Equal To (>=)')
#    LESS_EQUAL = 'LE', _('Less Than Equal To (<=)')

class SampleValueFilterForm(forms.Form):
    sample_value_name = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                               label="Sample Value Filter",
                                               required=False,
                                               widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                attrs={"data-allow-clear": "true",
                                                                                       "data-placeholder": "Select Sample Value name",
                                                                                       "style": "flex-grow: 1; width: 50%",
                                                                                       "data-html": True}))
    sample_value_comparator = forms.CharField(max_length=2)
#                                              choices=ValueComparator.choices,
#                                              default=ValueComparator.EQUAL)
    sample_value_comparison = forms.CharField(max_length=4096)

SampleValueFilterFormset = formset_factory(SampleValueFilterForm)

class SampleFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    analysis = django_filters.ModelMultipleChoiceFilter(queryset=Analysis.objects.all(), label="Related Analysis (results must be in at least one)", to_field_name="pk", field_name="results__analysis",
                                                        widget=autocomplete.ModelSelect2Multiple(url='object-analysis-autocomplete',
                                                                                         attrs={"data-allow-clear": "true",
                                                                                                "style": "flex-grow: 1",
                                                                                                "class": "form-control",
                                                                                                "data-html": True}))
    class Meta:
        model = Sample
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'

