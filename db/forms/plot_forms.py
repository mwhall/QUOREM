# ----------------------------------------------------------------------------
# path: quorem/db/forms/plot_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all plot input forms
# ----------------------------------------------------------------------------

from .fields import OrderedModelMultipleChoiceField
from django import forms
from ..models import (
    Investigation,
    Result,
    Sample, Feature,
    DataSignature
)

from django.forms import ModelForm

from dal import autocomplete

##### Plot Option Select Form

class TreeSelectForm(forms.Form):
    tree_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                         label="Phylogenetic Tree",
                                         widget=autocomplete.ModelSelect2(url='result-tree-autocomplete', attrs={"style": "flex-grow: 1", 'data-html': True}))

class TableCollapseForm(forms.Form):
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
    taxonomy_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                             label="Taxonomic Classification Set",
                                             widget=autocomplete.ModelSelect2(url='result-taxonomy-autocomplete',
                                                 forward=("count_matrix",),
                                                 attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
                                             
    normalize_methods = ["raw", "counts", "none", "proportion", "percent"]
    normalize_method = autocomplete.Select2ListChoiceField(choice_list=normalize_methods,
                                                           widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))

    tax_ranks = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species","Full"]
    taxonomic_level = autocomplete.Select2ListChoiceField(choice_list=tax_ranks,
                                                          widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))
    metadata_collapse = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Aggregation",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))

class PCoAPlotForm(forms.Form):
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
    measures = ['euclidean', 'l2', 'l1', 'manhattan', 'cityblock', 'braycurtis', 'canberra', 'chebyshev', 'correlation', 'cosine', 'dice', 'hamming', 'jaccard', 'kulsinski', 'mahalanobis', 'matching', 'minkowski', 'rogerstanimoto', 'russellrao', 'seuclidean', 'sokalmichener', 'sokalsneath', 'sqeuclidean', 'yule', 'wminkowski', 'nan_euclidean', 'haversine']
    measure = autocomplete.Select2ListChoiceField(required=True, choice_list=measures,
                                             widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                    'data-html': True}))
    metadata_colour = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Colour",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "data-placeholder": "Select metadata to colour Samples by",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))
    three_dimensional = forms.BooleanField(required=False, initial=False, label="3D Plot", widget=forms.CheckboxInput(attrs={"class":"big-checkbox"}))


class TablePlotForm(forms.Form):

    plot_types = ['bar', 'heatmap', 'area', 'box', 'violin']
    plot_type = autocomplete.Select2ListChoiceField(required=True, choice_list=plot_types,
                                             widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                    'data-html': True}))
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
    taxonomy_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                             label="Taxonomic Classification Set",
                                             widget=autocomplete.ModelSelect2(url='result-taxonomy-autocomplete',
                                                 forward=("count_matrix",),
                                                 attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
                                             
    normalize_methods = ["raw", "counts", "none", "proportion", "percent"]
    normalize_method = autocomplete.Select2ListChoiceField(choice_list=normalize_methods,
                                                           widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))

    tax_ranks = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species","Full"]
    taxonomic_level = autocomplete.Select2ListChoiceField(choice_list=tax_ranks,
                                                          widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))
    plot_height = forms.IntegerField(initial=750)
    metadata_collapse = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Aggregation",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "data-placeholder": "Select metadata to collapse Samples on",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))
    metadata_sort = OrderedModelMultipleChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Sort",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2Multiple(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))

    plot_height = forms.IntegerField(initial=750, label="Height (px)")
    n_taxa = forms.IntegerField(initial=25, label="Plot N Most Abundant Taxa")
    label_bars = forms.BooleanField(required=False, initial=True, label="Taxonomic Labels on Bars", widget=forms.CheckboxInput(attrs={"class":"big-checkbox"}))

class TaxBarSelectForm(forms.Form):
    taxonomy_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                             label="Taxonomic Classification Set",
                                             widget=autocomplete.ModelSelect2(url='result-taxonomy-autocomplete',
                                                                              attrs={"style": "flex-grow: 1;", 'data-html': True}))
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1", 'data-html': True}))
    samples_from_investigation = forms.ModelChoiceField(queryset=Investigation.objects.all(),
                                                        required=False,
                                                        label="Select Samples from Investigation",
                                                        widget=autocomplete.ModelSelect2(url='object-investigation-autocomplete',
                                                                                                 attrs={"data-allow-clear":"true",
                                                                                                        "style": "flex-grow: 1",
                                                                                                        "data-html": True}))
    samples = forms.ModelMultipleChoiceField(queryset=Sample.objects.all(),
                                          required=False,
                                          label="Samples",
                                          widget=autocomplete.ModelSelect2Multiple(url='object-sample-autocomplete',
                                                                                   forward=('count_matrix',),
                                                                                   attrs={"data-allow-clear": "true", "style": "flex-grow: 1", 'data-html': True}))
    taxonomic_level = autocomplete.Select2ListChoiceField(widget=autocomplete.ListSelect2(url='taxonomic-level-autocomplete', attrs={"style": "flex-grow: 1", 
        'data-html': True}))
    plot_height = forms.IntegerField(initial=750)
#    def __init__(self, *args, **kwargs):
#        super().__init__(*args, **kwargs)
#        self.fields['plot_height'].widget.attrs.update({'placeholder': 750,'default':750})
    metadata_sort_by = OrderedModelMultipleChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Sort",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2Multiple(url='data-signature-autocomplete',
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                      "style": "flex-grow: 1",
                                                                                                      "data-html": True}))
    plot_height = forms.IntegerField(initial=750, label="Height (px)")
    n_taxa = forms.IntegerField(initial=25, label="Plot N Most Abundant Taxa")
    label_bars = forms.BooleanField(initial=True, label="Taxonomic Labels on Bars", widget=forms.CheckboxInput(attrs={"class":"big-checkbox"}))

