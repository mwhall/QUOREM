from collections import OrderedDict, defaultdict
import string
import time
import ast
import urllib
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic.edit import CreateView
from django.http import JsonResponse
from django.urls import reverse as django_reverse, reverse_lazy
from django.utils.html import format_html, mark_safe
from django.db import models, utils
from django.http import Http404
from django.http import HttpResponseRedirect, FileResponse, HttpResponse
from django.core.paginator import(
    Paginator,
    EmptyPage,
    PageNotAnInteger,
)
from django.db.models import F, Q
from django.views.generic.base import TemplateView
from django.template.response import TemplateResponse

###Stuff for searching
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector
)
###django pandas
from django_pandas import io as django_pd
import django_filters
import tempfile
from io import BytesIO
from dal import autocomplete
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

import pandas as pd
import numpy as np
from celery import current_app

from .plot import *
from .ml import *
from .models import *
from .models.object import Object
from .forms import *
from .utils import barchart_html, trendchart_html, value_table_html


def reverse(*args, **kwargs):
    get = kwargs.pop('get', {})
    post = kwargs.pop('post', {})
    url = django_reverse(*args, **kwargs)
    if get:
        url += '?' + urllib.parse.urlencode(get)
    if post:
        postcopy = post.copy()
        postcopy.pop("csrfmiddlewaretoken")
        url += '?' + urllib.parse.urlencode(postcopy)
    return url

#def value_filter_view_factory(object_class):
#
#    class ValueFilterView(BaseFilterView):
#        # This is from django_jinja_knockout.views.base
#        # We need to override a bunch of functions to allow the filters
#        # to support our complex polymorphic Value fields
#        # TODO: Figure out how to wire this up completely
#
#        def __init__(self, *args, **kwargs):
#            field_set = set()
#            field_names = object_class.get_all_value_fields()
#            for value_type in field_names:
#                for name in field_names[value_type]:
#                    field_set.add(name+"_"+value_type)
#            self.field_names = list(field_set)
#            super().__init__(*args, **kwargs)
#
#        def get_field_verbose_name(self, field_name):
#            # str() is used to avoid "<django.utils.functional.__proxy__ object> is not JSON serializable" error.
#            if field_name in self.field_names:
#                return field_name
#            return super().get_field_verbose_name(field_name)
#
#        def get_related_fields(self, query_fields=None):
#            if query_fields is None:
#                query_fields = self.get_all_fieldnames() + self.field_names
#            return list(set(self.get_grid_fields_attnames()) - set(query_fields))
#
#        def get_all_fieldnames(self):
#            return super().get_all_fieldnames() + self.field_names
#
#    return ValueFilterView

###############################################################################
### Database Browse DJK views                                              ####
###############################################################################
class HomePageView(TemplateView):
    template_name= "homepage.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['feature_count'] = Feature.objects.count()
        context['sample_count'] = Sample.objects.count()
        context['result_count'] = Result.objects.count()
        return context

def main_page(request, **kwargs):
    return TemplateResponse(request, 'main.htm')

#    # get an object list to populate the carousel
#    def __init__(self, *args, **kwargs):
#        super().__init__(*args, **kwargs)
#        self.ob_list = [{'name': ob.base_name.capitalize(), 'info': ob.info(), 'link': ob.base_name + "/all/"} for ob in Object.get_object_types()]
#    def get_context_data(self, **kwargs):
#        context = super().get_context_data(**kwargs)
#        context['obj_list'] = self.ob_list
#        return context

## LIST VIEWS ##################################################################
#  These list *all* the objects of a given type                               ##
#  Things that are easily controlled here:                                    ##
#    - Which columns are in the table (grid_fields)                           ##
#    - Table filters (allowed_filter_fields; kinda complicated)               ##
#    - Titles                                                                 ##
#    - Formatting and filtering of values that are output to the table        ##
#  The core/custom_cbv_list.htm template is a lightly modified djk default    ##
#  to make the tables less garish and twitchy                                 ##
#                                                                             ##
#  Pages here:                                                                ##
#    - Upload (/upload/all)                                                   ##
#                                                                             ##
################################################################################

class UploadList(ListView):
    model = UploadFile
    allowed_sort_orders = '__all__'
    template_name = 'core/custom_cbv_list.htm'
    grid_fields = ['upload_file', 'upload_type', 'upload_status', 'userprofile']
    allowed_filter_fields = OrderedDict()

    @classmethod
    def update_list_filters(cls):
        return OrderedDict([
                            ('upload_type', {'type': 'choices', 'choices': UploadFile.objects.values_list("upload_type", "upload_type").distinct(), 'active_choices': []}),
                            ('upload_status', {'type': 'choices', 'choices': UploadFile.objects.values_list("upload_status", "upload_status").distinct(), 'active_choices': []}),
                            ('userprofile', {'type': 'choices', 'choices': UploadFile.objects.values_list("userprofile__pk", "userprofile__user__email").distinct(), 'active_choices': []}),
                            ])

    @classmethod
    def object_filter_fields(cls):
        ff = [x for x in cls.allowed_filter_fields]
        letters = string.ascii_uppercase[0:len(ff)]
        return [(idx,x) for idx, x in zip(letters, ff) if (x in cls.allowed_filter_fields)]

    def get_heading(self):
        return "Upload List"

    @classmethod
    def as_view(cls, *args, **kwargs):
       cls.allowed_filter_fields = cls.update_list_filters()
       return super().as_view(**kwargs)

#    def get_display_value(self, obj, field):
#        if field == "name":
#            return mark_safe(obj.get_detail_link())
#        return mark_safe(getattr(obj, field).get_detail_link())

    def get_table_attrs(self):
        return {
            'class': 'table table-bordered table-collapse display-block-condition custom-table',
            'id' : 'object_table',
        }

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('uploadfile_detail', kwargs={'uploadfile_id': obj.pk}),
            str(obj.upload_file)
        )]
        # is_authenticated is not callable in Django 2.0.
        return links

    def get_display_value(self, obj, field):
        if field == 'upload_file':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)

    def get_bs_form_opts(self):
        return {
            'title': "All Uploads",
            'view_title': "All Uploads",
            'submit_text': "Save Uploads"
        }

    @classmethod
    def reset_filter_link(cls):
        return reverse("upload_all")

## DETAIL VIEWS ################################################################
#  These list the details of one object of a given type                       ##
#  By overriding get_context_data we can intercept values and reformat        ##
#  by setting the get_text_method of the DisplayText widget, which loops      ##
#  over items if it's a manyto relationship, so should return one name        ##
#  Can also make CharFields in the DisplayForms and manually override their   ##
#  values either here or there.                                               ##
################################################################################

class UploadFileDetail(DetailView):
    is_new = False
    pk_url_kwarg = 'uploadfile_id'
    format_view_title = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if(self.is_new):
            context['new_upload'] = True
        return context

    def get_heading(self):
        return "Upload File Details"

## LIST VIEWS ##################################################################
###############################################################################

#Generic FilteredListView from caktusgroup.com/blog/2018/10/18/filtering-and-pagination-django/
class FilteredListView(ListView):
    filterset_class = None
    paginate_by = 20
    model = Object
    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs.distinct()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filterset'] = self.filterset
        context['base_name'] = self.model.base_name
        context['plural_name'] = self.model.plural_name
        return context

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

class FeatureFilterListView(FilteredListView):
    filterset_class = FeatureFilterSet
    template_name = "list.htm"
    model = Feature
    paginate_by = 15
#    def get_context_data(self, **kwargs):
#        context = super().get_context_data(**kwargs)
#        context['base_name'] = self.model.base_name
        
#        return context
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

class SampleFilterListView(FilteredListView):
    filterset_class = SampleFilterSet
    template_name = "list.htm"
    model = Sample
    paginate_by = 15

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

class StepFilterListView(FilteredListView):
    filterset_class = StepFilterSet
    template_name = "list.htm"
    model = Step
    paginate_by = 15

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

class InvestigationFilterListView(FilteredListView):
    filterset_class = InvestigationFilterSet
    template_name = "list.htm"
    model = Investigation
    paginate_by = 15

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

class ProcessFilterListView(FilteredListView):
    filterset_class = ProcessFilterSet
    template_name = "list.htm"
    model = Process
    paginate_by = 15

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

class AnalysisFilterListView(FilteredListView):
    filterset_class = AnalysisFilterSet
    template_name = "list.htm"
    model = Analysis
    paginate_by = 15

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

class ResultFilterListView(FilteredListView):
    filterset_class = ResultFilterSet
    template_name = "list.htm"
    model = Result
    paginate_by = 15


## CREATE VIEWS ################################################################
#  These allow the creation of one object of a given type                     ##
#  Here we can easily control:                                                ##
#    - Button names                                                           ##
#    - Form titles                                                            ##
#    - Templates for input forms (if the base doesn't work)                   ##
#    - Success URL routing                                                    ##
#                                                                             ##
#  Pages here:                                                                ##
#    - Investigation (/investigation/create)                                  ##
#    - Sample (/sample/create)                                                ##
#    - Feature (/feature/create)                                              ##
#    - Analysis (/analysis/create)                                            ##
#    - Step (/step/create)                                                    ##
#    - Process (/process/create)                                              ##
#    - Result (/result/create)                                                ##
#                                                                             ##
################################################################################
class InvestigationCreate(CreateView):
    form_class = InvestigationCreateForm
    model = Investigation
    template_name = "create.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_name'] = "investigation"
        return context

class SampleCreate(CreateView):
    format_view_title = True
    form = SampleForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Sample'}
    def get_heading(self):
        return "Create New Sample"

class FeatureCreate(CreateView):
    format_view_title = True
    form = FeatureForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Feature'}
    def get_heading(self):
        return "Create New Feature"

class AnalysisCreate(CreateView):
    form_class = AnalysisCreateForm
    model = Analysis
    template_name = "create.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_name'] = "analysis"
        return context

class StepCreate(CreateView):
    format_view_title = True
    form = StepForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Step'}
    def get_heading(self):
        return "Create New Step"

class ProcessCreate(CreateView):
    form_class = ProcessCreateForm
    model = Process
    template_name = "create.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_name'] = "process"
        return context




class InvestigationUpdate(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'investigation_id'
    form = InvestigationForm
    def get_bs_form_opts(self):
        return {
            'title': 'Edit Investigation',
            'submit_text': 'Save Investigation'
        }

class SampleUpdate(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'sample_id'
    form = SampleForm
    def get_bs_form_opts(self):
        return {
            'title': 'Edit Sample',
            'submit_text': 'Save Sample'
        }

class StepUpdate(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'step_id'
    form = StepForm
    def get_bs_form_opts(self):
        return {
            'title': 'Update Step',
            'submit_text': 'Save Step',
        }

    def get_success_url(self):
        return reverse('step_detail', kwargs={'step_id': self.object.pk})



class ProcessUpdate(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'process_id'
    form = ProcessForm
    def get_bs_form_opts(self):
        return {
            'title': 'Update Process',
            'submit_text': 'Save Process',
        }

    def get_success_url(self):
        return reverse('process_detail', kwargs={'process_id': self.object.pk})

class AnalysisSelectView(FormView):
    form_class = AnalysisSelectForm
    template_name = 'analysis_select.htm'
    def form_valid(self, form):
        self.analysis_pk = self.request.POST.get("analysis")
        return HttpResponseRedirect(self.get_success_url())
    def get_success_url(self):
        return reverse('upload_to_analysis', kwargs={"analysis_id": self.analysis_pk})


###############################################################################
### PLOT REDIRECTS                                                          ###
###############################################################################

class TaxBarSelectView(FormView):
    form_class = TaxBarSelectForm
    template_name = 'taxbarselect.htm'
    def post(self, request, *args, **kwargs):
        request.POST = request.POST.copy()
        samples = request.POST.getlist('samples','')
        if samples is not '':
            # Dict is immutable, so must copy
            # For some reason, any multi-selects lose all but the last element, 
            # so we pass it as a single string
            request.POST['samples'] = ",".join(request.POST.getlist('samples'))
        metadata_sort_by = request.POST.getlist('metadata_sort_by','')
        if metadata_sort_by is not '':
            request.POST['metadata_sort_by'] = ",".join(request.POST.getlist('metadata_sort_by'))
        return redirect(reverse('plot-tax-bar', post=request.POST))

class TreeSelectView(FormView):
    form_class = TreeSelectForm
    template_name = 'treeselect.htm'
    def post(self, request, *args, **kwargs):
        return redirect(reverse('plot-tree', post=request.POST))

#For feature correlation, re-use taxbar form.
class TaxCorrelationSelectView(FormView):
    form_class = TaxBarSelectForm
    template_name = 'analyze/correlation.htm'
    def post(self, request, *args, **kwargs):
        return redirect(reverse('plot-tax-correlation', post=request.POST))

###############################################################################
### SEARCH AND QUERY BASED VIEWS                                            ####
###############################################################################

#A simple function based view to GET the search bar form
def search(request):

    q_map = {'str val': 'str__value',
            'int val': 'int__value',
            'float val': 'float__value',}

    value_range = None
    meta_type = None
    facets = None
    ##MODEL INFO:::
    ## (logic_model_type, db_model_type, user_facing_model_string)
    model_types= [('investigation', Investigation, 'Investigations'),
                  ('sample', Sample, 'Samples'),
                  ('feature', Feature, 'Features'),
                  ('analysis', Analysis, 'Analyses'),
                  ('process', Process, 'Processes'),
                  ('step', Step, 'Steps' ),
                  ('result', Result, 'Results'),]

    ## Retrieve values from request
    #q or q2 is search term.
    q = request.GET.get('q', '').strip() #user input from search bar
    if not q:
        q = request.GET.get('q2', '').strip()

    ##From search form
    selected_type = request.GET.get('otype', '')
    meta = request.GET.get('meta', '')
    min_selected = request.GET.get('min_value', '')
    max_selected = request.GET.get('max_value', '')
    print("min max: ", min_selected, " ", max_selected)
    str_facets = request.GET.get("string_facets", '').split(sep=',')
    if str_facets[0] == '':
        str_facets = None
    #initialize vars for query
    query = None
    rank_annotation = None
    values = ['pk','otype']
    if q:
        query = SearchQuery(q)
        rank_annotation = SearchRank(F('search_vector'), query)
        values.append('rank')



   #Allows iterative building of queryset.
    def make_queryset(model_type, type_name):
        qs = model_type.objects.annotate(
            otype=models.Value(type_name, output_field=models.CharField())
        )
        #Filter metadata ranges
        if meta:
            qs = qs.filter(values__signature__name=meta) #only works with samples

            if min_selected and max_selected:
                vals = Value.objects.filter(signature__name=meta)
                filt = q_map[vals[0].signature.name]
                filt_lte = filt + "__lte"
                filt_gte = filt + "__gte"
                vals = vals.filter(**{filt_lte: max_selected, filt_gte: min_selected})
                qs = qs.filter(values__in=vals)
            if str_facets:
                print("string facets was true")
                qs = qs.filter(values__str__value__in=str_facets)

        qs = qs.distinct()
        if q:
            #SearchQuery matches with stemming, but not partial string matching.
            #icontains for partial matching. =query for SearchQuery functionality
            qs = qs.filter(Q(search_vector__icontains=q) | Q(search_vector = query))
            qs = qs.annotate(rank=rank_annotation)

        return qs.order_by()


    #Create an empty qs with the right 'shape' to build upon.
    #Model type is arbitrary.
    #Django will compile away the empty qs when making the query.
    qs = Investigation.objects.annotate(
        otype=models.Value('empty', output_field=models.CharField))

    if q:
        qs = qs.annotate(rank=rank_annotation)
    qs = qs.values(*values).none() #values for qs results

    #stuff for faceted search
    type_counts_raw = {}

    #Iteratively construct the query.
    for type_name, model_type, frontend_string in model_types:
        #If a type has been selected, only use that type.
        if selected_type and selected_type != type_name:
            continue
        this_qs = make_queryset(model_type, type_name)
        type_count = this_qs.count()
        if type_count:
            type_counts_raw[frontend_string] = {'count': type_count,
                                                'name': type_name}
        qs = qs.union(this_qs.values(*values))

    if q:
        qs = qs.order_by('-rank')

    #create a dict of types and counts to pass to the view.
    type_counts = sorted(
        [
            {'otype': type_name, 'n': value['count'], 'name': value['name']}
            for type_name, value in type_counts_raw.items()
        ],
        key=lambda t: t['n'], reverse=True
    )
    #use a pagintator.
    paginator = Paginator(qs, 20) #20 results per page
    page_number = request.GET.get('page') or '1'
    try:
        page = paginator.page(page_number)
        #will pass page to the context.
    except PageNotAnInteger:
        raise Http404('not an int')
    except EmptyPage:
        raise Http404('empty page')

    # qs now has a list of dicts corresponding to pks of objects in the db,
    # their type, and their search rank. Now, get the actual objects:
    results = []
    for obj in load_mixed_objects(page.object_list, model_types):
        results.append({
            'otype': obj.original_dict['otype'],
            'rank': obj.original_dict.get('rank'),
            'obj': obj,
        })

    if q:
        title= "Search Results for %s" % (q)
    else:
        title = 'Search'

    #selected Filters
    selected = {
        'otype': selected_type,
    }

    #present fitler options for each initial object type.
    if selected['otype']:
        q_string = {'sample' : 'samples__isnull',
                    'feature': 'features__isnull',
                    'result': 'results__isnull',
                    'step': 'steps__isnull',
                    'analysis': 'analyses__isnull',
                    'process': 'processes__isnull'}[selected['otype']]

        metadata = Value.objects.filter(**{q_string: False}).exclude(signature__value_type__in=[ContentType.objects.get_for_model(Version)]).order_by('signature__name').distinct('signature__name')

        if meta:
            vals = Value.objects.filter(**{q_string: False}).filter(signature__name=meta)
            meta_type = [ContentType.objects.get_for_id(x).model_class() for x in DataSignature.objects.filter(name=meta).values_list('data_types', flat=True).distinct()][0]
# need some logic to rpesent range filters for aplicable dtypes
    else:
        metadata = None

    #remove empty keys if there are any
    selected = {
        key: value
        for key, value in selected.items()
        if value
    }

    return render(request, 'search/search_results.htm',{
        'q':q,
        'qs': qs,
        'title':title,
        'results':results,
        'page_total': paginator.count,
        'page': page,
        'type_counts': type_counts,
        'selected': selected,
        'otype': selected_type,
        'metadata':metadata,
        'meta': meta,
        'meta_type': meta_type,
        'facets': facets,
        #selected values
        'string_facets': str_facets,
    #    'value_range': value_range,
        'min_value': min_selected,
        'max_value': max_selected,
        #'value_form': value_form,
            #'search_page': "active",
    })

###############################################################################
###          Analyse menu views                                           #####
###############################################################################

#Analysis portal view. Just a place holder for now
def analyze(request):
    return render(request, 'analyze/analyze.htm')

##Plot pages.
#Plotting landing page
def plot_view(request):
    return render(request, 'analyze/plot.htm')

class TreePlotView(TemplateView):
    template_name = "plot/treeplot.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tr = self.request.GET.get('tree_result','')
        feature_pks = self.request.GET.get('features','')
        show_names = self.request.GET.get('show_names','')
        show_names = False if show_names.lower() in ["", "false", "f", "no", "n", "0"] else True
        if feature_pks:
            feature_pks = [int(x) for x in feature_pks.split(",")]
        else:
            feature_pks = []
        plot = tree_plot(tr, feature_pks, show_names)
        context["plot_html"] = mark_safe(plot)
        return context

class TableCollapseView(FormView):
    template_name = "tablecollapse.htm"
    form_class = TableCollapseForm
    success_url = '/taxon-table/'

    def get_initial(self):
        initial = super().get_initial()
        initial['count_matrix'] = self.request.GET.get('count_matrix')
        initial['taxonomy_result'] = self.request.GET.get('taxonomy_result')
        initial['taxonomic_level'] = self.request.GET.get('taxonomic_level','genus').capitalize()
        initial['metadata_collapse'] = self.request.GET.get('metadata_collapse',None)
        initial['normalize_method'] = self.request.GET.get('normalize_method','proportion')
        return initial

    def form_valid(self, form):
        return redirect(reverse('tax_table_download'))

    def post(self, request, *args, **kwargs):
#        request.POST = request.POST.copy()
        #metadata_sort = request.POST.getlist('metadata_sort',None)
        #if metadata_sort != None:
        #    request.POST['metadata_sort'] = ",".join(request.POST.getlist('metadata_sort'))
        return redirect(reverse('tax_table_download'))

#    def get_context_data(self, **kwargs):
#        context = super().get_context_data(**kwargs)
#        cmr = self.request.GET.get('count_matrix','')
#        tr = self.request.GET.get('taxonomy_result','')
#        level = self.request.GET.get('taxonomic_level','genus')
#        metadata_collapse = self.request.GET.get('metadata_collapse',None)
#        metadata_sort = self.request.GET.get('metadata_sort',None)
#        normalize_method = self.request.GET.get('normalize_method','proportion')
#        if cmr and tr: #Minimum input to make a plot
#            plot_html = tax_bar_plot(tr, cmr, 
#                                     plot_height=plot_height,
#                                     level=level,
#                                     n_taxa=n_taxa,
#                                     normalize_method=normalize_method,
#                                     metadata_collapse=metadata_collapse,
#                                     metadata_sort=metadata_sort,
#                                     label_bars=label_bars).to_html()
#            context['plot_html'] = mark_safe(plot_html)
#        return context
#

class PCoAPlotView(FormView):
    template_name = "pcoaplot.htm"
    form_class = PCoAPlotForm

    def get_initial(self):
       initial = super().get_initial()
       initial['count_matrix'] = self.request.GET.get('count_matrix')
       initial['measure'] = self.request.GET.get('measure','braycurtis')
       initial['metadata_colour'] = self.request.GET.get('metadata_colour')
       initial['three_dimensional'] = self.request.GET.get('three_dimensional')
       return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cmr = self.request.GET.get('count_matrix','')
        measure = self.request.GET.get('measure','braycurtis')
        metadata_colour = self.request.GET.get('metadata_colour','')
        three_dimensional = self.request.GET.get('three_dimensional',False)
        if cmr: #Minimum input to make a plot
            plot_html = pcoa_plot(cmr,
                                  measure=measure,
                                  metadata_colour=metadata_colour,
                                  three_dimensional=three_dimensional).to_html()
            context['plot_html'] = mark_safe(plot_html)
        return context

class FeatureSelectPlotView(FormView):
    template_name = "featureselect.htm"
    form_class = FeatureSelectForm

    DEFAULT_METHOD = 'variance'
    DEFAULT_N_FEATURES = 100

    def get_initial(self):
       initial = super().get_initial()
       initial['count_matrix'] = self.request.GET.get('count_matrix')
       initial['method'] = self.request.GET.get('method',self.DEFAULT_METHOD)
       initial['n_features'] = self.request.GET.get('n_features', self.DEFAULT_N_FEATURES)
       return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cmr = self.request.GET.get('count_matrix','')
        method = self.request.GET.get('method',self.DEFAULT_METHOD)
        n_features = self.request.GET.get('n_features', self.DEFAULT_N_FEATURES)
        if cmr: #Minimum input to make a plot
            feature_html = feature_select(cmr,
                                  method=method,
                                  n_features=n_features)
            context['feature_html'] = mark_safe(feature_html)
        return context

class TablePlotView(FormView):
    template_name = "tableplot.htm"
    form_class = TablePlotForm

    def get_initial(self):
        initial = super().get_initial()
        initial['count_matrix'] = self.request.GET.get('count_matrix')
        initial['taxonomy_result'] = self.request.GET.get('taxonomy_result')
        initial['taxonomic_level'] = self.request.GET.get('taxonomic_level','genus').capitalize()
        initial['plot_height'] = int(self.request.GET.get('plot_height',750))
        initial['n_taxa'] = int(self.request.GET.get('n_taxa',10))
        initial['label_bars'] = bool(self.request.GET.get('label_bars',False))
        initial['metadata_collapse'] = self.request.GET.get('metadata_collapse',None)
        initial['metadata_sort'] = self.request.GET.getlist('metadata_sort',None)
        initial['normalize_method'] = self.request.GET.get('normalize_method','proportion')
        initial['plot_type'] = self.request.GET.get('plot_type','bar')
        return initial

    def get(self, request, *args, **kwargs):
        request.GET = request.GET.copy()
        print(dict(request.GET))
        if "metadata_collapse" in request.GET:
            if request.GET.get("metadata_collapse")=="" or request.GET.get("metadata_collapse")==None:
                request.GET.pop("metadata_collapse")
        print("GETTING TABLE PLOT")
        print(dict(request.GET))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cmr = self.request.GET.get('count_matrix','')
        tr = self.request.GET.get('taxonomy_result','')
        level = self.request.GET.get('taxonomic_level','genus')
        plot_height = int(self.request.GET.get('plot_height',1000))
        n_taxa = int(self.request.GET.get('n_taxa',10))
        label_bars = bool(self.request.GET.get('label_bars',False))
        metadata_collapse = self.request.GET.get('metadata_collapse',None)
        metadata_sort = self.request.GET.get('metadata_sort',None)
        normalize_method = self.request.GET.get('normalize_method','proportion')
        plot_type = self.request.GET.get('plot_type','bar')
        if cmr and tr: #Minimum input to make a plot
            plot_html = count_table_tax_plot(tr, cmr,
                                     plot_type=plot_type, 
                                     plot_height=plot_height,
                                     level=level,
                                     n_taxa=n_taxa,
                                     normalize_method=normalize_method,
                                     metadata_collapse=metadata_collapse,
                                     metadata_sort=metadata_sort,
                                     label_bars=label_bars).to_html()
            context['plot_html'] = mark_safe(plot_html)
        return context

class TaxBarPlotView(TemplateView):
    template_name = "taxbarplot.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tr = self.request.GET.get('taxonomy_result','')
        cmr = self.request.GET.get('count_matrix','')
        tl = self.request.GET.get('taxonomic_level','').lower()
        samples_from_investigation = self.request.GET.get('samples_from_investigation','')
        relative = self.request.GET.get('relative','')
        samples = self.request.GET.get('samples','')
        metadata_sort_by = self.request.GET.get('metadata_sort_by','')
        plot_height = self.request.GET.get('plot_height','')
        n_taxa = self.request.GET.get('n_taxa','')
        label_bars = self.request.GET.get('label_bars','')
        opt_kwargs = {}
        if samples != '':
            samples = samples.split(",")
            opt_kwargs["samples"] = [int(x) for x in samples]
        if tl != '':
            opt_kwargs["level"] = tl
        if relative != '':
            opt_kwargs["relative"] = False if relative.lower() in ["", "false", "f", "no", "n", "0"] else True
        if label_bars != '':
            opt_kwargs["label_bars"] = False if label_bars.lower() in ["", "false", "f", "no", "n", "0"] else True
        if plot_height != '':
            opt_kwargs["plot_height"] = int(plot_height)
        if n_taxa != '':
            opt_kwargs["n_taxa"] = int(n_taxa)
        if samples_from_investigation != '':
            opt_kwargs["samples_from_investigation"] = int(samples_from_investigation)
        if metadata_sort_by != "":
            metadata_sort_by = metadata_sort_by.split(",")
            opt_kwargs["metadata_sort_by"] = [int(x) for x in metadata_sort_by]
        plot_html = tax_bar_plot(tr,cmr,**opt_kwargs)
        context["plot_html"] = plot_html
        context["taxonomy_card"] = apps.get_model("db.Result").objects.get(pk=tr).bootstrap_card()
        context["matrix_card"] = apps.get_model("db.Result").objects.get(pk=cmr).bootstrap_card()
        return context

#plots correlation bewtween sample values and tax features.
class TaxCorrelationPlotView(TemplateView):
    template_name = "plot/taxcorrelationplot.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tr = self.request.GET.get('taxonomy_result','')
        cmr = self.request.GET.get('count_matrix','')
        tl = self.request.GET.get('taxonomic_level','').lower()
        relative = self.request.GET.get('relative','')
        opt_kwargs = {}
        if tl != '':
            opt_kwargs["level"] = tl
        if relative != '':
            opt_kwargs["relative"] = False if relative.lower() in ["", "false", "f", "no", "n", "0"] else True
        plot_html = tax_correlation_plot(tr,cmr,**opt_kwargs)
        context["plot_html"] = plot_html
        context["taxonomy_card"] = apps.get_model("db.Result").objects.get(pk=tr).bootstrap_card()
        context["matrix_card"] = apps.get_model("db.Result").objects.get(pk=cmr).bootstrap_card()
        return context

###############################################################################
### View for handling file uploads                                          ###
###############################################################################
class spreadsheet_upload(CreateView):
    form_class = SpreadsheetUploadForm
    template_name = 'core/uploadcard.htm'

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super(spreadsheet_upload, self).get_form_kwargs(*args, **kwargs)
        kwargs['userprofile'] = UserProfile.objects.get(user=self.request.user)
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        user = self.request.user
        userprofile = UserProfile.objects.get(user=user)
        self.object.userprofile = userprofile
        self.object.upload_type = "S"
        self.object.save()
        current_app.send_task('db.tasks.react_to_file', args=(self.object.pk,))
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('uploadfile_detail_new', kwargs={'uploadfile_id': self.object.pk,
                                                                    'new':"new"})
class simple_sample_metadata_upload(CreateView):
    form_class = SimpleMetadataUploadForm
    template_name = 'core/uploadcard-simple.htm'

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super(simple_sample_metadata_upload, self).get_form_kwargs(*args, **kwargs)
        kwargs['userprofile'] = UserProfile.objects.get(user=self.request.user)
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        user = self.request.user
        userprofile = UserProfile.objects.get(user=user)
        self.object.userprofile = userprofile
        self.object.upload_type = "M"
        self.object.save()
        current_app.send_task('db.tasks.react_to_file', args=(self.object.pk,),
        kwargs={'overwrite':form.cleaned_data['overwrite']})
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('uploadfile_detail_new', kwargs={'uploadfile_id': self.object.pk,
                                                                    'new':"new"})

class AnalysisFileFieldView(FormView):
    form_class = FileFieldForm
    template_name = 'analysis_upload.htm'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['analysis_name'] = Analysis.objects.get(pk=self.kwargs['analysis_id']).name
        context['analysis_id'] = self.kwargs['analysis_id']
        return context
    def post(self, request, *args, **kwargs):
        analysis = Analysis.objects.get(pk=self.kwargs['analysis_id'])
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file')
        if form.is_valid():
            user = User.objects.get(pk=self.request.user.pk)
            user_profile = UserProfile.objects.get(user=user)
            upload_time = datetime.datetime.now().strftime("%d_%b_%Y_%H%-M-%S")
            for f in files:
                # File type checking, crude for now
                if f.name.endswith("qza") or f.name.endswith("qzv"):
                    type_name = "artifacts"
                    upload_type = "A"
                elif f.name.endswith("csv") or f.name.endswith("tsv") or f.name.endswith("xls") or f.name.endswith("xlsx"):
                    type_name = "spreadsheets"
                    upload_type = "S"
                else:
                    return JsonResponse({"form": False})
                save_dir = Path(settings.MEDIA_ROOT + "/" + type_name + "/" + str(user.username) + "/" + str(upload_time) +"/")
                save_dir.mkdir(parents=True, exist_ok=True)
                save_dir = save_dir.resolve()
                print("User %s requesting to upload %s at time %s to Analysis '%s', placing in directory %s" % (user.username, f.name, upload_time, analysis.name, save_dir))
                file_path = str(save_dir) + "/" + f.name
                with open(file_path, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
                print("File successfully uploaded and stored on server, integrating into database...")
                #Save as a File object
                upload_file = UploadFile(upload_file=file_path, userprofile=user_profile, upload_type=upload_type)
                upload_file.save()
                print("File stored as UploadFile")
                current_app.send_task('db.tasks.react_to_file', (upload_file.pk,),
                                      kwargs={'analysis_pk': analysis.id})
                print("File sent to Celery for processing, standby for update...")
            return JsonResponse({'form': True, 'message': 'Success!', 'status':'success'})
        else:
            return JsonResponse({'form': False})

class SpreadsheetFileFieldView(FormView):
    form_class = FileFieldForm
    template_name = 'spreadsheet_upload.htm'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file')
        if form.is_valid():
            analysis = Analysis.objects.get(name="Spreadsheet Uploads")
            user = User.objects.get(pk=self.request.user.pk)
            user_profile = UserProfile.objects.get(user=user)
            upload_time = datetime.datetime.now().strftime("%d_%b_%Y_%H%-M-%S")
            save_dir = Path(settings.MEDIA_ROOT + "/spreadsheets/" + str(user.username) + "/" + str(upload_time) +"/")
            save_dir.mkdir(parents=True, exist_ok=True)
            save_dir = save_dir.resolve()
            for f in files:
                file_path = str(save_dir) + "/" + f.name
                print("User %s requesting to upload %s at time %s, placing in directory %s" % (user.username, f.name, upload_time, save_dir))
                with open(file_path, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
                print("File successfully uploaded and stored on server, integrating into database...")
                #Save as a File object
                upload_file = UploadFile(upload_file=file_path, userprofile=user_profile, upload_type='S')
                upload_file.save()
                print("File stored as UploadFile")
                current_app.send_task('db.tasks.react_to_file', (upload_file.pk,),
                        kwargs={'analysis_pk': analysis.pk})
                print("File sent to Celery for processing, standby for update...")
            return JsonResponse({'form': True, 'message': 'Success!', 'status':'success'})
        else:
            return JsonResponse({'form': False})


class artifact_upload(CreateView):
    form_class = ArtifactUploadForm
    template_name = 'upload_artifact.htm'

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super(artifact_upload, self).get_form_kwargs(*args, **kwargs)
        kwargs['userprofile'] = UserProfile.objects.get(user=self.request.user)
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        user = self.request.user
        userprofile = UserProfile.objects.get(user=user)
        self.object.userprofile = userprofile
        self.object.upload_type = "A"
        self.object.save()
        current_app.send_task('db.tasks.react_to_file', (self.object.pk,),
                kwargs={'analysis_pk': form.cleaned_data['analysis'].pk})
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('uploadfile_detail_new', kwargs={'uploadfile_id': self.object.pk,
                                                                           'new':"new"})

class MailBoxView(View):
    template_name="mail/mailbox.htm"
    def get(self, request):
        if request.user.is_authenticated:
            userProfile = UserProfile.objects.get(user=request.user)
            mailBox = UserMail.objects.filter(user=userProfile).order_by('-date_created')
            unread = mailBox.filter(read=False).count()
            return render(request, self.template_name, {'user':userProfile,
                                                        'mail': mailBox,
                                                        'unread': unread,
                                                        'active_page': 'mail',})

class MailOpen(View):
    template_name="mail/mailbox.htm"
    def get(self, request, mail_id):
        mail_pk = self.kwargs['mail_id']
        if request.user.is_authenticated:
            mail = UserMail.objects.get(pk=mail_pk)
            userProfile = UserProfile.objects.get(user=request.user)
            if mail.user != userProfile:
                print("nah")
                return
            mail.read = True
            mail.save()
            mailBox = UserMail.objects.filter(user=userProfile).order_by('-date_created')
            unread = mailBox.filter(read=False).count()
            return render(request, "mail/mailbox.htm", {'user':userProfile,
                                                        'mail': mailBox,
                                                        'unread': unread,
                                                        'active_page': 'mail',
                                                        'selected': mail,})


def xls_download_view(request):
    model_map =  {'investigation': Investigation,
                  'sample': Sample,
                  'feature': Feature,
                  'analysis': Analysis,
                  'process': Process,
                  'step': Step,
                  'result': Result,}

    q = request.GET.get('q', '').strip() #user input from search bar
    if not q:
        q = request.GET.get('q2', '').strip()

    ##From search form
    selected_type = request.GET.get('otype', '')
    meta = request.GET.get('meta', '')

    #initialize vars for query
    query = None
    if q:
        query = SearchQuery(q)

    klass = model_map[selected_type]
    plural = klass.plural_name

    if meta:
        qs = klass.objects.filter(values__signature__name__in=[meta]).annotate(value_name=F('values__signature__name'))
    else:
        qs = klass.objects.all().annotate(value_name=F('values__signature__name'))

    df = klass.dataframe(**{plural: qs})

    with BytesIO() as b:
        writer = pd.ExcelWriter(b, engine="xlsxwriter")
        df.to_excel(writer)
        writer.save()
        response = HttpResponse(b.getvalue(), content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="hello.xls"'
        return response


def tax_table_download_view(request):
    taxonomy_result = request.GET.get('taxonomy_result','')
    count_matrix = request.GET.get('count_matrix','')
    taxonomic_level = request.GET.get('taxonomic_level','genus')
    normalize_method = request.GET.get('normalize_method',"None")
    metadata_collapse = request.GET.get('metadata_collapse',None)
    collapsed_df = collapsed_table(taxonomy_result, count_matrix, 
                                   taxonomic_level, normalize_method, 
                                   metadata_collapse)
    filename_suffix = "_taxpk_%s_matrixpk_%s" % (str(taxonomy_result), str(count_matrix))
    filename_suffix += "_%s" % (str(taxonomic_level),)
    filename_suffix += "_%s" % (normalize_method,)
    if metadata_collapse is not None and metadata_collapse != '':
        filename_suffix += "_%s" % (metadata_collapse,)
    with BytesIO() as b:
        writer = pd.ExcelWriter(b, engine="xlsxwriter")
        collapsed_df.to_excel(writer)
        writer.save()
        response = HttpResponse(b.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="taxonomy_table%s.xlsx"' % (filename_suffix,)
        return response

def csv_download_view(request):

    model_map =  {'investigation': Investigation,
                  'sample': Sample,
                  'feature': Feature,
                  'analysis': Analysis,
                  'process': Process,
                  'step': Step,
                  'result': Result,}

    q = request.GET.get('q', '').strip() #user input from search bar
    if not q:
        q = request.GET.get('q2', '').strip()

    ##From search form
    selected_type = request.GET.get('otype', '')
    meta = request.GET.get('meta', '')

    #initialize vars for query
    query = None
    if q:
        query = SearchQuery(q)

    klass = model_map[selected_type]
    plural = klass.plural_name
    if meta:
        qs = klass.objects.filter(values__signature__name__in=[meta]).annotate(value_name=F('values__signature__name'))
    else:
        qs = klass.objects.all().annotate(value_name=F('values__signature__name'))

    df = klass.dataframe(**{plural: qs})
    csv = df.to_csv()
    response = HttpResponse(csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hello.csv"'
    return response


def no_auth_view(request):
    return render(request, 'core/noauth.htm')


def spreadsheet_download_view(request):
    id = request.GET.get('id', '')
    obj = request.GET.get('object','')
    wide = request.GET.get('wide','')
    format = request.GET.get('format', 'csv')
    result_id = request.GET.get('result_id', '')
    if result_id:
        result = Result.objects.get(pk=result_id)
        assert result.has_value("uploaded_spreadsheet", "file")
        artifact = result.get_value("uploaded_spreadsheet", "file").upload_file.file
        filename = artifact.name.split("/")[-1]
        response = HttpResponse(artifact.file, content_type='csv')
        response['Content-Disposition'] = 'attachment; filename="%s"' % (filename,)
        return response
    if str(wide).lower() in ["1", "true"]:
        wide = True
    else:
        wide = False
    Obj = Object.get_object_types(type_name=obj)
    df = Obj.objects.get(pk=id).dataframe(wide=wide)
    if format.lower() == "csv":
        df = df.to_csv()
        response = HttpResponse(df, content_type='text/csv')
    elif format.lower() in ["xls", "xlsx"]:
        with BytesIO() as b:
            writer = pd.ExcelWriter(b, engine="xlsxwriter")
            df.to_excel(writer)
            writer.save()
            response = HttpResponse(b.getvalue(), content_type='application/vnd.ms-excel')
    else:
        raise ValueError("Unrecognized spreadsheet format '%s'" % (format,))
    return response


def artifact_download_view(request):
    result_id = request.GET.get('result_id', '')
    if result_id:
        result = Result.objects.get(pk=result_id)
        assert result.has_value("uploaded_artifact", "file")
        artifact = result.get_value("uploaded_artifact", "file").upload_file.file
        filename = artifact.name.split("/")[-1]
        response = HttpResponse(artifact.file, content_type='zip/qza')
        response['Content-Disposition'] = 'attachment; filename="%s"' % (filename,)
        return response

