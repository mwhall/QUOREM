from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import CreateView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.messages import get_messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django.db import models
from django.http import Http404
from django.http import HttpResponseRedirect
from django.contrib.contenttypes.models import ContentType

from django.contrib.auth import get_user_model

from django.core.paginator import(
    Paginator,
    EmptyPage,
    PageNotAnInteger,
)
from django_jinja_knockout.views import (
        BsTabsMixin, ListSortingView, InlineCreateView, InlineCrudView, InlineDetailView,
        FormDetailView, FormatTitleMixin, FormViewmodelsMixin, FormWithInlineFormsetsMixin,
)


import django_tables2 as tables
import io
from collections import OrderedDict

from .formatters import guess_filetype
from .models import (
        Sample, Investigation, Process, Analysis,
        Step, Result, Feature, Value, Category,
        File, load_mixed_objects, UserProfile, UserMail
)

from .forms import *
"""
 (
    InvestigationDisplayForm, InvestigationForm,
    ProcessForm, ProcessDisplayForm,
    ResultDisplayForm,
    AnalysisDisplayForm, AnalysisForm,
    SampleDisplayForm, SampleForm,
    FeatureDisplayForm, FeatureForm,
    StepDisplayForm, StepForm,
    UploadForm, UserWithInlineUploads, FileDisplayForm,
    FileDisplayWithInlineErrors,
    SpreadsheetUploadForm, ArtifactUploadForm,
    AggregatePlotForm, AggregatePlotInvestigation, TrendPlotForm, ValueTableForm
)
"""
from .utils import barchart_html, trendchart_html

import pandas as pd
import numpy as np
import zipfile
import arrow
from celery import current_app

###Stuff for searching
from django.contrib.postgres.search import(
    SearchQuery, SearchRank, SearchVector)

from django.db.models import F, Q
from django.db.models.functions import Cast
from django.views.generic.edit import CreateView, FormView
from django.views.generic import TemplateView

###############################################################################
### Database Browse DJK views                                              ####
###############################################################################

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
#    - Investigation (/investigation/all)                                     ##
#    - Sample (/sample/all)                                                   ##
#    - Feature (/feature/all)                                                 ##
#    - Analysis (/analysis/all)                                               ##
#    - Step (/step/all)                                                       ##
#    - Process (/process/all)                                                 ##
#    - Result (/result/all)                                                   ##
#    - Upload (/upload/all)                                                   ##
#                                                                             ##
################################################################################

class InvestigationList(ListSortingView):
    model = Investigation
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    grid_fields = ['name', 'institution', 'description']

    def __init__(self, *args, **kwargs):
        content_type = ContentType.objects.get(app_label='db',
                                               model="investigation")
        self.allowed_filter_fields = OrderedDict([
            ('categories',
            {
                  'type': 'choices',
                  'choices': [(x['pk'], x['name']) for x in Category.objects.filter(category_of=content_type).values("pk","name").order_by("name")]
            })])
        super(InvestigationList, self).__init__(*args, **kwargs)

    def get_heading(self):
        return "Investigation List"

    def edit_investigation(self, obj):
        return format_html(
           ' (<a href="{}"><span class="iconui iconui-edit"></span></a>) ',
           reverse('investigation_update', kwargs={'investigation_id': obj.pk}))

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('investigation_detail', kwargs={'investigation_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(self.edit_investigation(obj))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        elif field == 'categories':
            cats = [x.name for x in obj.categories.all()]
            return mark_safe(', '.join(cats))
        else:
            return super().get_display_value(obj, field)

    def get_bs_form_opts(self):
        return {
            'title': "All Investigations",
            'view_title': "All Investigations",
            'submit_text': "Save Investigation",
        }

class SampleList(ListSortingView):
    model = Sample
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    grid_fields = ['name', 'investigations']
    def __init__(self, *args, **kwargs):
        content_type = ContentType.objects.get(app_label='db',
                                               model="sample")
        self.allowed_filter_fields = OrderedDict([
                ('categories',
                {
                      'type': 'choices',
                      'choices': [(x['pk'], x['name']) for x in Category.objects.filter(category_of=content_type).values("pk","name").order_by("name")]
                })])
        super(SampleList, self).__init__(*args, **kwargs)

    def get_heading(self):
        return "Sample List"

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('sample_detail', kwargs={'sample_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('sample_update', kwargs={'sample_id': obj.pk})
            ))
        return links

    def get_investigation_links(self, obj):
        links = [x.get_detail_link() \
          for x in obj.investigations.all() ]
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        elif field == 'investigations':
            links = self.get_investigation_links(obj)
            return mark_safe(', '.join(links))
        else:
            return super().get_display_value(obj, field)

class FeatureList(ListSortingView):
    model = Feature
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    grid_fields = ['name', 'sequence', 'annotations']
    def __init__(self, *args, **kwargs):
        content_type = ContentType.objects.get(app_label='db',
                                               model="feature")
        self.allowed_filter_fields = OrderedDict([
                ('categories',
                {
                      'type': 'choices',
                      'choices': [(x['pk'], x['name']) for x in Category.objects.filter(category_of=content_type).values("pk","name").order_by("name")]
                })])
        super(FeatureList, self).__init__(*args, **kwargs)

    def get_heading(self):
        return "Feature List"

    def get_name_links(self, obj):
        return obj.get_detail_link()

    def get_display_value(self, obj, field):
        if field=='name':
            return self.get_name_links(obj)

class AnalysisList(ListSortingView):
    model = Analysis
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    def __init__(self, *args, **kwargs):
        content_type = ContentType.objects.get(app_label='db',
                                               model="analysis")
        self.allowed_filter_fields = OrderedDict([
                ('process',
                {
                    'type': 'choices',
                    'choices': [(x['pk'], x['name']) for x in Process.objects.all().values("pk","name").distinct().order_by("name")],
                }),
                # BROKEN. There is a Date filter in DJK but it doesn't seem to work
                # with our field? And using a Choices filter raises that a Datetime
                # isn't serializable, and I don't know how else to get equality to
                # filter properly
                #('date',
                #{'type': None
                # 'choices': [(str(x['date']),str(x['date'])) \
                #              for x in Analysis.objects.all().values("date").distinct().order_by("date")]}),
                ('location',
                {
                     'type': 'choices',
                     'choices': [(x['location'], x['location']) for x in Analysis.objects.all().values("pk","location").distinct().order_by("location")]
                }),
                ('categories',
                {
                      'type': 'choices',
                      'choices': [(x['pk'], x['name']) for x in Category.objects.filter(category_of=content_type).values("pk","name").order_by("name")]
                })])
        super(AnalysisList, self).__init__(*args, **kwargs)
    grid_fields = ['name', 'process', 'date', 'location']

    def get_heading(self):
        return "Analysis List"

    def get_display_value(self, obj, field):
        if field == 'name':
            return obj.get_detail_link()
        elif field == 'date':
            return str(arrow.get(obj.date).format("DD/MM/YYYY"))
        elif field == 'process':
            return obj.process.get_detail_link()

class StepList(ListSortingView):
    model = Step
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    grid_fields = ['name', 'values']
    def __init__(self, *args, **kwargs):
        content_type = ContentType.objects.get(app_label='db',
                                               model="step")
        self.allowed_filter_fields = OrderedDict([
                ('categories',
                {
                      'type': 'choices',
                      'choices': [(x['pk'], x['name']) for x in Category.objects.filter(category_of=content_type).values("pk","name").order_by("name")]
                })])
        super(StepList, self).__init__(*args, **kwargs)
    def get_heading(self):
        return "Step List"
    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('step_detail', kwargs={'step_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('step_update', kwargs={'step_id': obj.pk})
            ))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        elif field == 'values':
            default_params = [x.name + ": " + str(x.content_object.value) \
                               for x in obj.values.annotate(stepcount=models.Count("steps")).filter(stepcount=1).filter(processes__isnull=True, samples__isnull=True, analyses__isnull=True, results__isnull=True) ]
            return mark_safe('</br>'.join(default_params))
        else:
            return super().get_display_value(obj, field)

class ProcessList(ListSortingView):
    model = Process
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    grid_fields = ['name', 'description']
    def __init__(self, *args, **kwargs):
        content_type = ContentType.objects.get(app_label='db',
                                               model="process")
        self.allowed_filter_fields = OrderedDict([
                ('categories',
                {
                      'type': 'choices',
                      'choices': [(x['pk'], x['name']) for x in Category.objects.filter(category_of=content_type).values("pk","name").order_by("name")]
                })])
        super(ProcessList, self).__init__(*args, **kwargs)

    def get_heading(self):
        return "Process List"

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('process_detail', kwargs={'process_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('process_update', kwargs={'process_id': obj.pk})
            ))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)

class ResultList(ListSortingView):
    model = Result
    allowed_sort_orders = '__all__'
    template_name = "core/custom_cbv_list.htm"
    def __init__(self, *args, **kwargs):
        self.allowed_filter_fields = OrderedDict([('type',
                {
                    'type': 'choices',
                    'choices': [(x['type'], x['type']) for x in Result.objects.all().values("type").distinct().order_by("type")],
                    # Do not display 'All' choice which resets the filter:
                    # List of choices that are active by default:
                    'active_choices': [],
                    # Do not allow to select multiple choices:
                }),
                ('source_step',
                {
                    'type': 'choices',
                    'choices': [(x['pk'], x['name']) for x in Step.objects.all().values("pk","name").distinct().order_by("name")],
                    # Do not display 'All' choice which resets the filter:
                    # List of choices that are active by default:
                    'active_choices': [],
                    # Do not allow to select multiple choices:
                })])
        super(ResultList, self).__init__(*args, **kwargs)

    grid_fields = ['uuid', 'analysis',  'source', 'type', 'source_step', 'file']

    def get_heading(self):
        return "Result List"

    def get_file_links(self, obj):
        links = []
        if obj.file is not None:
            links = [format_html(
                '<a href="{}">{}</a>',
                reverse('file_detail', kwargs={'file_id': obj.file.pk}),
                obj.file.upload_file
            )]
        #can anonymous users download files???? For now, yes...
        #though the website 404s if not logged in.
        #Only succrss files can be downloaded.
            if obj.file.upload_status == 'S':
                links.append(format_html(
                    ' (<a href="{}" target="_blank" data-toggle="tooltip" data-placement="top" title="Download"><span class="iconui iconui-download"></span></a>)',
                    #reverse('file_detail', kwargs={'file_id': obj.file.pk})
                    "/" + obj.file.upload_file.url
                ))
                links.append(format_html(
                ' (<a href="{}" target="_blank" data-toggle="tooltip" data-placement="top" title="View in Q2View"><span class="iconui iconui-eye-open"></span></a>)',
                "https://view.qiime2.org/visualization/?type=html&src=http://localhost:8000/" + obj.file.upload_file.url
                ))
        return links

    def get_display_value(self, obj, field):
        if field == 'file':
            links = self.get_file_links(obj)
            return mark_safe(''.join(links))
            #return self.get_file_name(obj)
        elif field == 'values':
            values = ", ".join(np.unique([x.name for x in obj.values.all()]))
            return values
        elif field == 'samples':
            samples = mark_safe(', '.join(np.unique([x.get_detail_link() for x in obj.samples.all()])))
            return samples
        elif field == 'features':
            feats = ', '.join(np.unique([x.name for x in obj.features.all()]))
            return feats
        elif field == 'source_step':
            if obj.source_step:
                return obj.source_step.get_detail_link()
        elif field == 'uuid':
            return obj.get_detail_link()
        else:
            return super().get_display_value(obj, field)

    def get_table_attrs(self):
        return {
            'class': 'table table-bordered table-collapse display-block-condition custom-table',
            'id' : 'result_table',
        }

class UploadList(ListSortingView):
    model = File
    allowed_sort_orders = '__all__'
    template_name = 'core/custom_cbv_list.htm'
    grid_fields = ['upload_file', 'upload_status','userprofile']

    def get_heading(self):
        return "Upload List"

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('file_detail', kwargs={'file_id': obj.pk,}),
            obj.upload_file
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

## DETAIL VIEWS ################################################################
#  These list the details of one object of a given type                       ##
#  By overriding get_context_data we can intercept values and reformat        ##
#  by setting the get_text_method of the DisplayText widget, which loops      ##
#  over items if it's a manyto relationship, so should return one name        ##
#  Can also make CharFields in the DisplayForms and manually override their   ##
#  values either here or there.                                               ##
#                                                                             ##
#  Pages here:                                                                ##
#    - Investigation (/investigation/###)                                     ##
#    - Sample (/sample/###)                                                   ##
#    - Feature (/feature/###)                                                 ##
#    - Analysis (/analysis/###)                                               ##
#    - Step (/step/###)                                                       ##
#    - Process (/process/###)                                                 ##
#    - Result (/result/###)                                                   ##
#    - Upload (/upload/###)                                                   ##
#                                                                             ##
################################################################################

class InvestigationDetail(InlineDetailView):
    pk_url_kwarg = 'investigation_id'
    form = InvestigationDisplayForm
    def get_heading(self):
        return ""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print([x for x in vars(context['form'].fields['institution'].widget)])
        # An example of what we've been doing in the forms.py being done here
        #context['form'].fields['institution'].widget.get_text_method = self.get_institution_name
        return context

class SampleDetail(InlineDetailView):
    pk_url_kwarg = 'sample_id'
    form = SampleDisplayForm
    def get_heading(self):
        return ""

class FeatureDetail(InlineDetailView):
    pk_url_kwarg = "feature_id"
    form = FeatureDisplayForm
    def get_heading(self):
        return ""
#    def get_context_data(self, **kwargs):
#        context['form'].fields['measures'].widget.get_text_method =

class AnalysisDetail(InlineDetailView):
    pk_url_kwarg = 'analysis_id'
    form = AnalysisDisplayForm
    def get_heading(self):
        return ""

class StepDetail(InlineDetailView):
    pk_url_kwarg = "step_id"
    form = StepDisplayForm
    def get_heading(self):
        return ""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #context['form'].initial['parameters'] = [x for x in context['object'].parameters.annotate(stepcount=models.Count("steps")).filter(stepcount=1).filter(processes__isnull=True, samples__isnull=True, analyses__isnull=True, results__isnull=True) ]
        return context

class ProcessDetail(InlineDetailView):
    pk_url_kwarg = 'process_id'
    form = ProcessDisplayForm
    def get_heading(self):
        return ""

class ResultDetail(InlineDetailView):
    pk_url_kwarg = 'result_id'
    form = ResultDisplayForm
    def get_heading(self):
        return ""

class FileDetail(InlineDetailView):
    is_new = False
    pk_url_kwarg = 'file_id'
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
            if selected_type == 'step':
                qs = qs.filter(values__name=meta)

            #this works with sample, feature, result. step needs another
            else:
                qs = qs.filter(values__name=meta) #only works with samples

            if min_selected and max_selected:
                vals = Value.objects.filter(name=meta)
                filt = q_map[vals[0].content_type.name]
                filt_lte = filt + "__lte"
                filt_gte = filt + "__gte"
                vals = vals.filter(**{filt_lte: max_selected, filt_gte: min_selected})
                qs = qs.filter(values__in=vals)
            if str_facets:
                print("string facets was true")
                qs = qs.filter(values__str__value__in=str_facets)

        #We need to be able to accomodate different choices for meta.
        #Not every filtered object will have 'values'

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

    #Find value ranges for relevant queries.

    ###########################################################################
    ### TODO: With new db, this if/else can be replaced with generic statements.

    if selected['otype'] == 'sample':
        metadata = Value.objects.filter(samples__isnull=False).order_by('name').distinct('name')
        if meta:
            vals = Value.objects.filter(samples__isnull=False).filter(name=meta)
            meta_type = vals[0].content_type.name
            filt = q_map[meta_type]
            vals = vals.order_by(filt).distinct()
            facets = [v.content_object.value for v in vals]

    elif selected['otype'] == 'step':
        metadata = Value.objects.filter(steps__isnull=False).order_by('name').distinct('name')

    elif selected['otype'] == 'feature':
        metadata = Value.objects.filter(features__isnull=False).order_by('name').distinct('name')

    elif selected['otype'] == 'result':
        metadata = Value.objects.filter(results__isnull=False).order_by('name').distinct('name')

    #Those 4 are all that make sense right now. later, allow selection of
    #analysis, investigation, process as an "query in" option

    else:
        metadata = None
    #/TODO
    ###########################################################################

    #remove empty keys if there are any
    selected = {
        key: value
        for key, value in selected.items()
        if value
    }
    if facets:
        print(meta_type)
        print(facets)
    return render(request, 'search/search_results.htm',{
        'q':q,
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


###############################################################################
### Trend Analysis Views                                                    ###
###############################################################################

class ValueTableView(FormView):
    template_name="search/value_tables.htm"
    form_class = ValueTableForm
    action = "plot_trend" #change this after
    success_url = '/values/'

    def get_context_data(self, *args, **kwargs):
        context = super(ValueTableView, self).get_context_data(**kwargs)
        context['action'] = self.action
        return context

#ajax view for populating Value Names based on Selected Model
def ajax_value_table_view(request):
    klass_map = {'1': (Investigation, 'investigations__in'),
                 '2': (Sample, 'samples__in'),
                 '3': (Feature, 'features__in'),
                 '4': (Step, 'steps__in'),
                 '5': (Process, 'processes__in'),
                 '6': (Analysis, 'analyses__in'),
                 '7': (Result, 'results__in'),}
    #this variable is passed to the reuqest by JS
    klass_tuple = klass_map[request.GET.get('object_klass')]
    klass = klass_tuple[0]
    q = klass_tuple[1]
    #gives a qs with the distinct names of values ass. w the selected class
    qs = Value.objects.filter(**{q: klass.objects.all()}).distinct().values_list('name', flat=True)

    return render(request, 'search/ajax_value_names.htm', {'qs': qs})



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
        html, choices= trendchart_html(req['invField'], req['x_val'], req['x_val_category'],
                                        req['y_val'], req['y_val_category'], req['operation_choice'])
        return render(self.request, '/analyze/plot_trend.htm', {'graph':html, 'choices':choices, 'action':self.action})


# View for x choices. Will need to populate x-val choices based on Investigations
# selected as well as x_val_category. Example, if choice is BB samples, populate
# with metadata found in BB. If two or more invs are selected, need to only show
# options found in all invs.

#trendx_view is the same as aggregate view for now. This may change at some point which is why
# its a seperate function.
def ajax_plot_trendx_view(request):
    inv_id = request.GET.getlist('inv_id[]')
    #if only one id is selected, not a list.
    if not inv_id:
        inv_id = request.GET.get('inv_id')
    model_choice = request.GET.get('otype')
    exclude = request.GET.get('exclude')

    qs = None
    otype = None

    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

    if model_choice == "1": #Samples
        qs = Value.objects.filter(samples__in=Sample.objects.filter(investigations=inv_id)).order_by('name').distinct('name')
        otype = "sample"

    elif model_choice == "2": #Features
        otype = "feature"
    return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

#trend y view will need to know what was chosen in trend x.
def ajax_plot_trendy_view(request):
    """
    vars from ajax:
    otype: model for y, as an integer.
    x_model: model for x, as an integr.
    x_choice: meta for x, as a string.
    """

    inv_id = request.GET.getlist('inv_id[]')
    #if only one id is selected, not a list.
    if not inv_id:
        inv_id = request.GET.get('inv_id')

    model_choice = request.GET.get('otype')
    x_model = request.GET.get('x_model')
    x_sel = request.GET.get('x_choice')

    qs = None
    otype = None

    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':qs,})

    xqs = None
    #X was sample
    if x_model == '1':
    #    xqs = Sample.objects.filter(values__in=Value.objects.filter(samples__in=Sample.objects.filter(investigation__in=inv_id)).filter(name=x_sel))
        x = Value.objects.filter(samples__in=Sample.objects.filter(investigations=inv_id)).filter(name=x_sel)
        xqs = Sample.objects.filter(values__in=x)
        otype = 'sample'
    yops = None
    if xqs:
        yops = Value.objects.filter(samples__in=xqs).order_by('name').distinct('name')
    return render (request, 'analyze/ajax_model_options.htm', {'otype': otype, 'qs':yops,})

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
        return reverse('file_detail_new', kwargs={'file_id': self.object.pk,
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
        current_app.send_task('db.tasks.react_to_file', (self.object.pk,), kwargs={'analysis_pk': form.fields['analysis']._queryset[0].pk,
                                                                                   'register_provenance': form['register_provenance'].value()})
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('file_detail_new', kwargs={'file_id': self.object.pk,
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


def testView(request):
    return render(request, 'newlanding.htm')
