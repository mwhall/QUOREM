# ----------------------------------------------------------------------------
# path: quorem/db/forms/feature_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all feature related forms
# ----------------------------------------------------------------------------

import django_filters
from dal import autocomplete

from django import forms
from django.utils.html import mark_safe
from ..models import *

from django.forms import ModelForm

class FeatureDetailForm(ModelForm):
    class Meta:
        model = Feature
        exclude = ['search_vector', 'values']

def filter_feature_by_taxonomy(queryset, name, value):
    # Start with a bunch of Features and reduce them to the ones that have a "taxonomic_classification" StrDatum attached with the matching query
    queryset = queryset.filter(values__in=Value.objects.filter(measure__data__in=StrDatum.objects.filter(value__icontains=value),
                                                               signature__name="taxonomic_classification"))
    return queryset

class FeatureFilterSet(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label="Name Contains")
    taxonomy = django_filters.CharFilter(label="Taxonomic Classification Contains", field_name="taxonomy", method=filter_feature_by_taxonomy)
    analysis = django_filters.ModelMultipleChoiceFilter(queryset=Analysis.objects.all(), label="Related Analysis (results must be in at least one)", to_field_name="pk", field_name="results__analysis",
                                                        widget=autocomplete.ModelSelect2Multiple(url='object-analysis-autocomplete',
                                                                                         attrs={"data-allow-clear": "true",
                                                                                                "style": "flex-grow: 1;",
                                                                                                "class": "form-control",
                                                                                                "data-html": True}))
    sample = django_filters.ModelMultipleChoiceFilter(queryset=Sample.objects.all(), label="Related Samples (results must be in at least one)", to_field_name="pk", field_name="samples",
                                                        widget=autocomplete.ModelSelect2Multiple(url='object-sample-autocomplete',
                                                                                         attrs={"data-allow-clear": "true",
                                                                                                "style": "flex-grow: 1;",
                                                                                                "class": "form-control",
                                                                                                "data-html": True}))
    class Meta:
        model = Feature
        fields = ['name']
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        #Put defaults in here
        super().__init__(data, *args, **kwargs)
        for visible in self.form.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'
