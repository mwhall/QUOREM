from collections import OrderedDict, defaultdict
import string
import ast
import urllib

from django.shortcuts import render, redirect
from django.views import View
from django.views.generic.edit import CreateView
from django.http import JsonResponse
from django.urls import reverse as django_reverse
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
from django.views.generic.edit import FormView
from django.views.generic.base import TemplateView

###Stuff for searching
from django.contrib.postgres.search import (
    SearchQuery, SearchRank, SearchVector
)
###django pandas
from django_pandas import io as django_pd
import tempfile
from io import BytesIO


from django_jinja_knockout.views import (
        BsTabsMixin, ListSortingView, InlineCreateView, InlineCrudView, InlineDetailView,
        ViewmodelView, BaseFilterView
)

import pandas as pd
import numpy as np
from celery import current_app

from .plot import *
from .models import *
from .models.object import Object
from .forms import *
from .utils import barchart_html, trendchart_html, value_table_html

#Stuff for dash
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

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

def value_filter_view_factory(object_class):

    class ValueFilterView(BaseFilterView):
        # This is from django_jinja_knockout.views.base
        # We need to override a bunch of functions to allow the filters
        # to support our complex polymorphic Value fields
        # TODO: Figure out how to wire this up completely

        def __init__(self, *args, **kwargs):
            field_set = set()
            field_names = object_class.get_all_value_fields()
            for value_type in field_names:
                for name in field_names[value_type]:
                    field_set.add(name+"_"+value_type)
            self.field_names = list(field_set)
            super().__init__(*args, **kwargs)

        def get_field_verbose_name(self, field_name):
            # str() is used to avoid "<django.utils.functional.__proxy__ object> is not JSON serializable" error.
            if field_name in self.field_names:
                return field_name
            return super().get_field_verbose_name(field_name)

        def get_related_fields(self, query_fields=None):
            if query_fields is None:
                query_fields = self.get_all_fieldnames() + self.field_names
            return list(set(self.get_grid_fields_attnames()) - set(query_fields))

        def get_all_fieldnames(self):
            return super().get_all_fieldnames() + self.field_names

    return ValueFilterView

###############################################################################
### Database Browse DJK views                                              ####
###############################################################################
class HomePage(BsTabsMixin, ViewmodelView):
    format_view_title=True
    template_name= "core/homepage.htm"
    # get an object list to populate the carousel
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ob_list = [{'name': ob.base_name.capitalize(), 'info': ob.info(), 'link': ob.base_name + "/all/"} for ob in Object.get_object_types()]
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['obj_list'] = self.ob_list
        return context

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

class UploadList(ListSortingView):
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

class UploadFileDetail(InlineDetailView):
    is_new = False
    pk_url_kwarg = 'uploadfile_id'
    form_with_inline_formsets = FileDisplayWithInlineErrors
    format_view_title = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if(self.is_new):
            context['new_upload'] = True
        return context

    def get_heading(self):
        return "Upload File Details"


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


class InvestigationCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    form = InvestigationForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context

    def get_heading(self):
        return "Create New Investigation"
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Investigation'}
    def get_success_url(self):
        return reverse('investigation_detail', kwargs={'investigation_id': self.object.pk})

class SampleCreate(BsTabsMixin, InlineCreateView):
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

class FeatureCreate(BsTabsMixin, InlineCreateView):
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

class AnalysisCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    form = AnalysisForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Analysis'}
    def get_heading(self):
        return "Create New Analysis"

class StepCreate(BsTabsMixin, InlineCreateView):
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

class ProcessCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    form = ProcessForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_heading(self):
        return "Create New Process"
    def get_bs_form_opts(self):
        return {
            'title': 'Create Process',
            'submit_text': 'Save Process',
            'inline_title': 'Process Steps'
        }
    def get_success_url(self):
        return reverse('process_detail', kwargs={'process_id': self.object.pk})



class InvestigationUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'investigation_id'
    form = InvestigationForm
    def get_bs_form_opts(self):
        return {
            'title': 'Edit Investigation',
            'submit_text': 'Save Investigation'
        }

class SampleUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'sample_id'
    form = SampleForm
    def get_bs_form_opts(self):
        return {
            'title': 'Edit Sample',
            'submit_text': 'Save Sample'
        }

class StepUpdate(BsTabsMixin, InlineCrudView):
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



class ProcessUpdate(BsTabsMixin, InlineCrudView):
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

###############################################################################
### PLOT REDIRECTS                                                          ###
###############################################################################

class TaxBarSelectView(FormView):
    form_class = TaxBarSelectForm
    template_name = 'core/taxbarselect.htm'
    def post(self, request, *args, **kwargs):
        return redirect(reverse('plot-tax-bar', post=request.POST))

class TreeSelectView(FormView):
    form_class = TreeSelectForm
    template_name = 'core/treeselect.htm'
    def post(self, request, *args, **kwargs):
        return redirect(reverse('plot-tree', post=request.POST))


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

################################################################################
## Aggregate Views!                                                            #
################################################################################

class PlotAggregateView(FormView):
        template_name = 'analyze/plot_aggregate.htm'
        form_class = AggregatePlotInvestigation
        action = 'plot_aggregate'
        success_url = '/analyze/'

        def get_context_data(self, *args, **kwargs):
            context = super(PlotAggregateView, self).get_context_data(**kwargs)
            context['action'] = self.action
            return context

        def form_invalid(self, form):
            print(form.errors)
            return super().form_invalid(form)

        def form_valid(self, form):
            req = self.request.POST
            inv = req.getlist('invField')
            html, choices = barchart_html(req['agg_choice'], inv, req['modelField'],
                                req.getlist('metaValueField'))
            return render(self.request, 'analyze/plot_aggregate.htm', {'graph':html, 'choices': choices, 'investigation': inv, 'action':self.action})


#ajax view for populating metaValue Field
#This view generates html for metavalue selection and populates a template
#The template html is passed to the view via AJAX javascript; 'aggregation_form.js'
def ajax_aggregates_meta_view(request):
    inv_id = request.GET.getlist('inv_id[]')
    #if only one id is selected, not a list.
    if not inv_id:
        inv_id = request.GET.get('inv_id')
    model_choice = request.GET.get('otype')
    exclude = request.GET.get('exclude')
    #get investigation specific meta data.
    #E.g. Inv -> Samples -> SampleMetadata
    qs = None
    otype = None

    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

    if model_choice == "1": #Samples
#        qs = SampleMetadata.objects.filter(
#            sample__in = Sample.objects.filter(
#            investigation__in = inv_id
#            )).order_by('key').distinct('key')
        #excludes are defined in each conditional to allow later flexibility
#        if exclude:
#            qs = qs.exclude(key=exclude)
        #With making investigations manytomany in Samples, this __in probably is broken...
        qs = Value.objects.filter(samples__in=Sample.objects.filter(investigations=inv_id)).order_by('name').distinct('name')
        otype = "sample"
    elif model_choice == "2": #Features
        qs = Value.objects.filter(features__isnull=False).order_by('name').distinct('name')
        otype = "feature"
#    elif model_choice == '3': #Computational something or other
    return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

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

class TaxBarPlotView(TemplateView):
    template_name = "plot/taxbarplot.htm"
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
        plot_html = tax_bar_plot(tr,cmr,**opt_kwargs)
        context["plot_html"] = plot_html
        context["taxonomy_card"] = apps.get_model("db.Result").objects.get(pk=tr).bootstrap_card()
        context["matrix_card"] = apps.get_model("db.Result").objects.get(pk=cmr).bootstrap_card()
        return context

###############################################################################
### Trend Analysis Views                                                    ###
###############################################################################

class ValueTableView(FormView):
    template_name="search/value_tables.htm"
    form_class = ValueTableForm
    action = 'value_table' #change this after
    success_url = '/values/'

    def get_context_data(self, *args, **kwargs):
        context = super(ValueTableView, self).get_context_data(**kwargs)
        context['action'] = self.action
        return context

    def form_invalid(self, form):
        print(form.errors)
        return super().form_invalid(form)

    def form_valid(self, form):
        print("form Valid!")
        req = self.request.POST
        x_selected = {}
    #    y_selected = {}
        x_selected[req.get('depField')] = req.getlist('depValue')
        i = 0
    #    key_name = 'indField_%s' % (i,)
        print(req)
#        while req.get(key_name):
#            val_name = 'indValue_%s' % (i,)
#            y_selected[req.get(key_name)] = req.getlist(val_name)
#            i += 1
#            key_name = 'indField_%s' % i

        html = value_table_html(x_selected)
        """
        inv = req.getlist('invField')
        html, choices = barchart_html(req['agg_choice'], inv, req['modelField'],
                            req.getlist('metaValueField'))
        """
        return render(self.request, 'search/value_tables.htm', {'table': html, 'action': self.action, 'form':self.form_class()})

#ajax view for populating Value Names based on Selected Model
def ajax_value_table_view(request):
    print("value name view was accessed")
    klass_map = {'1': (Investigation, 'investigations__isnull'),
                 '2': (Sample, 'samples__isnull'),
                 '3': (Feature, 'features__isnull'),
                 '4': (Step, 'steps__isnull'),
                 '5': (Process, 'processes__isnull'),
                 '6': (Analysis, 'analyses__isnull'),
                 '7': (Result, 'results__isnull'),}


    #this variable is passed to the reuqest by JS
    klass_tuple = klass_map[request.GET.get('object_klass')]
    klass = klass_tuple[0]
    q = klass_tuple[1]
    #gives a qs with the distinct names of values ass. w the selected class
#    qs = Value.objects.filter(**{q: klass.objects.all()}).distinct().values_list('name', flat=True)
    qs = Value.objects.filter(**{q: False}).order_by('signature__name').distinct('signature__name').values_list('signature__name', flat=True)
    return render(request, 'search/ajax_value_names.htm', {'qs': qs})

def ajax_value_table_related_models_view(request):
    #translate from input to query
    klass_map = {'1': (Investigation, 'investigations__in'),
                 '2': (Sample, 'samples__in'),
                 '3': (Feature, 'features__in'),
                 '4': (Step, 'steps__in'),
                 '5': (Process, 'processes__in'),
                 '6': (Analysis, 'analyses__in'),
                 '7': (Result, 'results__in'),}
    #use to populate form from results of this view
    reverse_klass_map = {'investigations': ('1', 'Investigation'),
                         'samples': ('2', 'Sample'),
                         'features': ('3', 'Feature'),
                         'steps': ('4', 'Step'),
                         'processes': ('5', 'Process'),
                         'analyses': ('6', 'Analysis'),
                         'results': ('7', "Results"),
                        }

    klass_tuple = klass_map[request.GET.get('object_klass')]
    klass = klass_tuple[0]
    q = klass_tuple[1]
    value_names = request.GET.getlist('vals[]') #getlist?
    vqs = Value.objects.filter(**{q:klass.objects.all()}, signature__name__in=value_names)
    dd = defaultdict(set)
    for val in vqs:
        links_dict = val.get_links()
        for key, value in links_dict.items():
            dd[key].update(value)
    linked_objects = dict(dd)
    # Right now have a dict of all possible objects.
    # Current logic prevents using more than just the names, so use them for now.
    klasses = list(linked_objects.keys())
    klass_list = [reverse_klass_map[k] for k in klasses]
    klass_list.insert(0, ('', "Select..."))
    #pass the class list to html snippet, which will be used to populate form
    return render(request, 'search/ajax_value_names_y.htm', {'options': klass_list})

class PlotTrendView(FormView):
    template_name="analyze/plot_trend.htm"
    form_class = TrendPlotForm
    action = "plot_trend"
    success_url = '/analyze/'

    def get_context_data(self, *args, **kwargs):
        context = super(PlotTrendView, self).get_context_data(**kwargs)
        context['action'] = self.action
        return context

    def form_invalid(self, form):
        return super().form_invalid(form)

    def form_valid(self, form):
        req = self.request.POST
        html, choices= trendchart_html(req['x_val'], req['x_val_category'],
                                        req['y_val'], req['operation_choice'])
        return render(self.request, '/analyze/plot_trend.htm', {'graph':html, 'choices':choices, 'action':self.action})


# View for x choices. Will need to populate x-val choices based on Investigations
# selected as well as x_val_category. Example, if choice is BB samples, populate
# with metadata found in BB. If two or more invs are selected, need to only show
# options found in all invs.

#trendx_view is the same as aggregate view for now. This may change at some point which is why
# its a seperate function.
def ajax_plot_trendx_view(request):
    print("HI")

    model_choice = request.GET.get('type')
    print(model_choice)
    exclude = request.GET.get('exclude')

    qs = None
    otype = None

    type_map = {'1': (Sample, 'sample'),
                '2': (Feature, 'feature'),
                '3': (Result, ''),}

    q_string = {'1' : 'samples__isnull',
                '2': 'features__isnull',
                '3': 'results__isnull',
                #'step': 'steps__isnull',
                #'analysis': 'analyses__isnull',
                #'process': 'processes__isnull',
                }[model_choice]

    qs = Value.objects.filter(**{q_string: False}).exclude(
        signature__value_type__in=[ContentType.objects.get_for_model(Version)]).order_by(
        'signature__name').distinct('signature__name').values_list(
        'signature__name', flat=True)
    print(qs)
    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'otype': type, 'qs':qs,})

    return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

#trend y view will need to know what was chosen in trend x.
def ajax_plot_trendy_view(request):
    x_model = request.GET.get('x_model')
    x_sel = request.GET.get('x_choice')

    q_tuple = {'1' : (Sample, 'samples__in'),
                '2': (Feature, 'features__in'),
                '3': (Result, 'results__in'),
                #'step': 'steps__isnull',
                #'analysis': 'analyses__isnull',
                #'process': 'processes__isnull',
                }[x_model]

    qs = None

    if not x_model:
        return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

    xqs = None
    klass = q_tuple[0]
    q_string = q_tuple[1]

    xqs = klass.objects.filter(values__signature__name__in=[x_sel])
    yops = None
    if xqs:
        yops = Value.objects.filter(**{q_string: xqs}).exclude(signature__value_type__in=[ContentType.objects.get_for_model(Version)]).order_by('signature__name').distinct('signature__name').values_list('signature__name', flat=True)
    print("YOPS")
    print(yops)
    return render (request, 'analyze/ajax_model_options.htm', {'qs':yops,})

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


class artifact_upload(CreateView):
    form_class = ArtifactUploadForm
    template_name = 'core/uploadcard_artifact.htm'

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
################################################################################
## onto testing                                                              ###
###############################################################################

def onto_view(request):
    return render(request, 'ontology/ontoview.htm', {'active_page': 'ontology'})

import json
def onto_json(request):
    with open('ontology/ontology.json', 'r') as f:
        onto = json.load(f)
    return JsonResponse(onto)


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


## DASH APPS
# These need to be here or in urls.py apparently.
