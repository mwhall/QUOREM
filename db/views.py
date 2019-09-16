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

from .formatters import guess_filetype
from .models import (
        Sample, Investigation, Process,
        Step, Result, Feature, Value,
        UploadInputFile, load_mixed_objects, UserProfile
)

from .forms import (
    InvestigationDisplayWithInlineSamples, InvestigationWithInlineSamples,
    ProcessForm, ProcessDisplayWithInlineSteps, ProcessWithInlineSteps,
    ResultDisplayForm,
    SampleDisplayForm, SampleForm, StepForm,
    UploadForm, UserWithInlineUploads, UploadInputFileDisplayForm,
    UploadInputFileDisplayWithInlineErrors, NewUploadForm,
    AggregatePlotForm, AggregatePlotInvestigation, TrendPlotForm
)
from .utils import barchart_html, trendchart_html

import pandas as pd
import numpy as np
import zipfile

###Stuff for searching
from django.contrib.postgres.search import(
    SearchQuery, SearchRank, SearchVector)

from django.db.models import F, Q
from django.db.models.functions import Cast
from django.views.generic.edit import CreateView, FormView

###############################################################################
### Database Browse DJK views                                              ####
###############################################################################
class UploadList(ListSortingView):
    model = UploadInputFile
    allowed_sort_orders = '__all__'
    grid_fields = ['upload_file', 'upload_status','userprofile']

    def get_heading(self):
        return "Upload List"

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': obj.pk,}),
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
            'view_title': "All Uploads2",
            'submit_text': "Save Uploads????"
        }

class UploadInputFileDetail(InlineDetailView):
    is_new = False
    pk_url_kwarg = 'uploadinputfile_id'
    form_with_inline_formsets = UploadInputFileDisplayWithInlineErrors
    format_view_title = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if(self.is_new):
            context['new_upload'] = True
        return context

    def get_heading(self):
        return "Upload File Details"

class InvestigationList(ListSortingView):
    model = Investigation
    allowed_sort_orders = '__all__'
    #allowed_filter_fields = {'description': None}
    grid_fields = ['name', 'institution', 'description']
    list_display = ['edit_investigation']
    def get_heading(self):
        return "Investigation List"
    def edit_investigation(self, obj):
        return format_html(
           '<a href="{}"><span class="iconui iconui-edit"></span></a>',
           reverse('investigation_update', kwargs={'investigation_id': obj.pk}))

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('investigation_detail', kwargs={'investigation_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>',
                reverse('investigation_update', kwargs={'investigation_id': obj.pk})
            ))
        # TODO: Fix metadata display
        #    links.append(format_html(
        #        ' <a href="{}"><span class="iconui iconui-file"></span></a>)',
        #        reverse('investigation_metadata_detail', kwargs={'investigation_id': obj.pk})
        #    ))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)

    def get_bs_form_opts(self):
        return {
            'title': "All Investigations",
            'view_title': "All Investigations",
            'submit_text': "Save Investigation",
        }

class InvestigationDetail(InlineDetailView):
    pk_url_kwarg = 'investigation_id'
    #template_name = 'investigation_edit.htm'
    form_with_inline_formsets = InvestigationDisplayWithInlineSamples

class InvestigationUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'investigation_id'
    form_with_inline_formsets = InvestigationWithInlineSamples
    def get_bs_form_opts(self):
        return {
            'title': format_html('Edit "{}"', self.object),
            'submit_text': 'Save Investigation'
        }

class InvestigationCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'investigation_id'
    form_with_inline_formsets = InvestigationWithInlineSamples
    def get_heading(self):
        return "Create New Investigation"
    def get_bs_form_opts(self):
        return {
            'submit_text': 'Save Investigation'
        }

    def get_success_url(self):
        return reverse('investigation_detail', kwargs={'investigation_id': self.object.pk})

class SampleList(ListSortingView):
    model = Sample
    allowed_sort_orders = '__all__'
    grid_fields = ['name', 'investigation']
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
        links = [format_html(
            '<a href="{}">{}</a>',
             reverse('investigation_detail', kwargs={'investigation_id': obj.investigation.pk}),
             obj.investigation.name
         )]
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        elif field == 'investigation':
            links = self.get_investigation_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)


class SampleDetail(InlineDetailView):
    pk_url_kwarg = 'sample_id'
    form = SampleDisplayForm

class SampleUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'sample_id'
    form = SampleForm
    def get_bs_form_opts(self):
        return {
            'submit_text': 'Save Sample'
        }

class FeatureList(ListSortingView):
    model = Feature
    allowed_sort_orders = '__all__'

class StepList(ListSortingView):
    model = Step
    allowed_sort_orders = '__all__'
    grid_fields = ['name']
    def get_heading(self):
        return "Step List"
#    def get_name_links(self, obj):
#        links = [format_html(
#            '<a href="{}">{}</a>',
#            reverse('step_detail', kwargs={'step_id': obj.pk}),
#            obj.name
#        )]
#        # is_authenticated is not callable in Django 2.0.
#        if self.request.user.is_authenticated:
#            links.append(format_html(
#                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
#                reverse('step_update', kwargs={'step_id': obj.pk})
#            ))
#        return links

#    def get_display_value(self, obj, field):
#        if field == 'name':
#            links = self.get_name_links(obj)
#            return mark_safe(''.join(links))
#        else:
#            return super().get_display_value(obj, field)

class StepCreate(CreateView):
    template_name = "base.htm"
    model = Step
    form_class = StepForm

class ResultList(ListSortingView):
    model = Result
    allowed_sort_orders = '__all__'
    grid_fields = ['uuid', 'input_file', 'source', 'type', 'samples', 'features', ['analysis', 'source_step'], 'values']
    def get_heading(self):
        return "Result List"

    def get_file_links(self, obj):
        links = []
        if obj.input_file is not None:
            links = [format_html(
                '<a href="{}">{}</a>',
                reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': obj.input_file.pk}),
                obj.input_file.upload_file
            )]
        #can anonymous users download files???? For now, yes...
        #though the website 404s if not logged in.
        #Only succrss files can be downloaded.
            if obj.input_file.upload_status == 'S':
                links.append(format_html(
                    ' (<a href="{}" target="_blank" data-toggle="tooltip" data-placement="top" title="Download"><span class="iconui iconui-download"></span></a>)',
                    #reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': obj.input_file.pk})
                    "/" + obj.input_file.upload_file.url
                ))
                links.append(format_html(
                ' (<a href="{}" target="_blank" data-toggle="tooltip" data-placement="top" title="View in Q2View"><span class="iconui iconui-eye-open"></span></a>)',
                "https://view.qiime2.org/visualization/?type=html&src=http://localhost:8000/" + obj.input_file.upload_file.url
                ))
        return links

    def get_display_value(self, obj, field):
        if field == 'input_file':
            links = self.get_file_links(obj)
            return mark_safe(''.join(links))
            #return self.get_file_name(obj)
        elif field == 'values':
            values = ", ".join(np.unique([x.name for x in obj.values.all()]))
            return values
        elif field == 'samples':
            samples = ', '.join(np.unique([x.name for x in obj.samples.all()]))
            return samples
        elif field == 'features':
            feats = ', '.join(np.unique([x.name for x in obj.features.all()]))
            return feats
        else:
            return super().get_display_value(obj, field)

    def get_table_attrs(self):
        return {
            'class': 'table table-bordered table-collapse display-block-condition custom-table',
            'id' : 'result_table',
        }

class ProcessList(ListSortingView):
    model = Process
    allowed_sort_orders = '__all__'
    grid_fields = ['name']
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


class ProcessDetail(InlineDetailView):
    pk_url_kwarg = 'process_id'
    form_with_inline_formsets = ProcessDisplayWithInlineSteps

class ProcessCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'process_id'
    form_with_inline_formsets = ProcessWithInlineSteps
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

class ProcessUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'process_id'
    form_with_inline_formsets = ProcessWithInlineSteps
    def get_bs_form_opts(self):
        return {
            'title': 'Update Process',
            'submit_text': 'Save Process',
        }

    def get_success_url(self):
        return reverse('process_detail', kwargs={'process_id': self.object.pk})

class ResultDetail(InlineDetailView):
    pk_url_kwargs = 'result_id'


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
                  ('replicate', Replicate, 'Replicates'),
                  ('process', Process, 'Processs'),
                  ('processStep', Step, 'Computational Process Step' ),]

    ## Retrieve values from request
    #q or q2 is search term.
    q = request.GET.get('q', '').strip() #user input from search bar
    if not q:
        q = request.GET.get('q2', '').strip()

    ##From search form
    selected_type = request.GET.get('type', '')
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
    values = ['pk','type']
    if q:
        query = SearchQuery(q)
        rank_annotation = SearchRank(F('search_vector'), query)
        values.append('rank')



   #Allows iterative building of queryset.
    def make_queryset(model_type, type_name):
        qs = model_type.objects.annotate(
            type=models.Value(type_name, output_field=models.CharField())
        )
        #Filter metadata ranges
        if meta:
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
        type=models.Value('empty', output_field=models.CharField))

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
            {'type': type_name, 'n': value['count'], 'name': value['name']}
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
            'type': obj.original_dict['type'],
            'rank': obj.original_dict.get('rank'),
            'obj': obj,
        })

    if q:
        title= "Search Results for %s" % (q)
    else:
        title = 'Search'

    #selected Filters
    selected = {
        'type': selected_type,
    }

    #Find value ranges for relevant queries.

    ###########################################################################
    ### TODO: With new db, this if/else can be replaced with generic statements.

    if selected['type'] == 'sample':
        metadata = Value.objects.filter(samples__in=Sample.objects.all()).order_by('name').distinct('name')
        if meta:
            vals = Value.objects.filter(samples__in=Sample.objects.all()).filter(name=meta)
            meta_type = vals[0].content_type.name
            filt = q_map[meta_type]
            vals = vals.order_by(filt).distinct()
            facets = [v.content_object.value for v in vals]
            print("facets should be in order now: ", facets)

    elif selected['type'] == 'replicate':
        metadata = Value.objects.filter(replicates__in=Replicate.objects.all()).order_by('name').distinct('name')
        if meta:
            vals = Value.objects.filter(replicates__in=Replicate.objects.all()).filter(name=meta)
            meta_type = vals[0].content_type.name
            facets = list(set([v.content_object.value for v in vals]))

    elif selected['type'] == 'processStep':
        metadata = Value.objects.filter(steps__in=Step.objects.all()).order_by('name').distinct('name')

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
        'type': selected_type,
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
    model_choice = request.GET.get('type')
    exclude = request.GET.get('exclude')
    #get investigation specific meta data.
    #E.g. Inv -> Samples -> SampleMetadata
    #     Inv -> Reps -> ReplicateMetadata
    qs = None
    type = None

    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':qs,})

    if model_choice == "1": #Samples
#        qs = SampleMetadata.objects.filter(
#            sample__in = Sample.objects.filter(
#            investigation__in = inv_id
#            )).order_by('key').distinct('key')
        #excludes are defined in each conditional to allow later flexibility
#        if exclude:
#            qs = qs.exclude(key=exclude)
        qs = Value.objects.filter(samples__in=Sample.objects.filter(investigation__in=inv_id)).order_by('name').distinct('name')
        type = "sample"
    elif model_choice == "2": #Bio Replicates
#        qs = ReplicateMetadata.objects.filter(
#            biological_replicate__in = (Replicate.objects.filter(
#            sample__in = Sample.objects.filter(investigation__in = inv_id)
#            ))).order_by('key').distinct('key')
#        if exclude:
#            qs = qs.exclude(key=exclude)
        type = "replicate"
#    elif model_choice == '3': #Computational something or other
    return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':qs,})


###############################################################################
### Trend Analysis Views                                                    ###
###############################################################################

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
    model_choice = request.GET.get('type')
    exclude = request.GET.get('exclude')

    qs = None
    type = None

    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':qs,})

    if model_choice == "1": #Samples
        qs = Value.objects.filter(samples__in=Sample.objects.filter(investigation__in=inv_id)).order_by('name').distinct('name')
        type = "sample"

    elif model_choice == "2": #Bio Replicates
        type = "replicate"
    return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':qs,})

#trend y view will need to know what was chosen in trend x.
def ajax_plot_trendy_view(request):
    """
    vars from ajax:
    type: model for y, as an integer.
    x_model: model for x, as an integr.
    x_choice: meta for x, as a string.
    """

    inv_id = request.GET.getlist('inv_id[]')
    #if only one id is selected, not a list.
    if not inv_id:
        inv_id = request.GET.get('inv_id')

    model_choice = request.GET.get('type')
    x_model = request.GET.get('x_model')
    x_sel = request.GET.get('x_choice')

    qs = None
    type = None

    if not model_choice:
        return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':qs,})

    xqs = None
    #X was sample
    if x_model == '1':
    #    xqs = Sample.objects.filter(values__in=Value.objects.filter(samples__in=Sample.objects.filter(investigation__in=inv_id)).filter(name=x_sel))
        x = Value.objects.filter(samples__in=Sample.objects.filter(investigation__in=inv_id)).filter(name=x_sel)
        xqs = Sample.objects.filter(values__in=x)
        type = 'sample'
    yops = None
    if xqs:
        yops = Value.objects.filter(samples__in=xqs).order_by('name').distinct('name')
    return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':yops,})

###############################################################################
### View for handling file uploads                                          ###
###############################################################################
class new_upload(CreateView):
    form_class = NewUploadForm
    template_name = 'core/uploadcard.htm'

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super(new_upload, self).get_form_kwargs(*args, **kwargs)
        kwargs['userprofile'] = UserProfile.objects.get(user=self.request.user)
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        user = self.request.user
        userprofile = UserProfile.objects.get(user=user)
        self.object.userprofile = userprofile
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('uploadinputfile_detail_new', kwargs={'uploadinputfile_id': self.object.pk,
                                                                    'new':"new"})
