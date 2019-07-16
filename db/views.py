from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import ListView
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
        Sample, SampleMetadata, Investigation, BiologicalReplicateProtocol,
        ProtocolStep, BiologicalReplicate, BiologicalReplicateMetadata,
        ComputationalPipeline, PipelineStep, PipelineStepParameter,
        UploadInputFile, load_mixed_objects, UserProfile
)

from .forms import (
    InvestigationDisplayWithInlineSamples, InvestigationWithInlineSamples,
    ProtocolForm, ProtocolDisplayWithInlineSteps,
    ProtocolStepWithInlineParameters, ProtocolStepDisplayWithInlineParameters,
    ProtocolWithInlineSteps,
    PipelineForm, PipelineDisplayWithInlineSteps, PipelineResult,
    PipelineStepWithInlineParameters, PipelineStepDisplayWithInlineParameters,
    PipelineWithInlineSteps, ReplicateDisplayWithInlineMetadata,
    ReplicateWithInlineMetadata, SampleDisplayWithInlineMetadata,
    SampleWithInlineMetadata, UploadForm, UserWithInlineUploads, UploadInputFileDisplayForm,
    UploadInputFileDisplayWithInlineErrors, NewUploadForm,
    AggregatePlotForm, AggregatePlotInvestigation
)
from .utils import barchart_html

import pandas as pd
import numpy as np
import zipfile

###Stuff for searching
from django.contrib.postgres.search import(
    SearchQuery, SearchRank, SearchVector)

from django.db.models import F
from django.db.models.functions import Cast
from django.views.generic.edit import CreateView, FormView

'''
Class-based Django-Jinja-Knockout views
'''

"""
###############################################################################
Deprecated June 14, 2019. Leave in for ~a month in case of bugs with new_upload.
###############################################################################

class UploadCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    form_class = UserProfileForm
    pk_url_kwarg = 'userprofile_id'

    form_with_inline_formsets = UserWithInlineUploads


    def get_bs_form_opts(self):
        return {
                'title': 'Upload Files',
               'submit_text': 'Upload',
                }

    def get_success_url(self):
        return reverse('uploadinputfile_detail_new', kwargs={'uploadinputfile_id': self.object.pk -1,
                                                            'new':"new"})
"""


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
            links.append(format_html(
                ' <a href="{}"><span class="iconui iconui-file"></span></a>)',
                reverse('investigation_metadata_detail', kwargs={'investigation_id': obj.pk})
            ))
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
            'view_title': "All Investigations2",
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
    form_with_inline_formsets = SampleDisplayWithInlineMetadata

class SampleUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'sample_id'
    form_with_inline_formsets = SampleWithInlineMetadata
    def get_bs_form_opts(self):
        return {
            'submit_text': 'Save Sample'
        }

class InvestigationMetadataDetail(ListSortingView):
    model = SampleMetadata
    allowed_sort_orders = '__all__'
    grid_fields = ['sample__name', 'key', 'value']
    #Override the queryset to return the investigation id requested
    def get_heading(self):
        return "Sample Metadata for Investigation \"%s\"" % (Investigation.objects.get(pk=self.kwargs['investigation_id']).name,)
    def get_queryset(self):
        return SampleMetadata.objects.filter(sample__investigation_id=self.kwargs['investigation_id'])

class ReplicateList(ListSortingView):
    model = BiologicalReplicate
    allowed_sort_orders = '__all__'
    grid_fields = ['name', 'sample']
    def get_heading(self):
        return "Replicate List"
    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('replicate_detail', kwargs={'replicate_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('replicate_update', kwargs={'replicate_id': obj.pk})
            ))
        return links

    def get_sample_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
             reverse('sample_detail', kwargs={'sample_id': obj.sample.pk}),
             obj.sample.name
         )]
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        elif field == 'sample':
            links = self.get_sample_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)


class ReplicateDetail(InlineDetailView):
    pk_url_kwarg = 'replicate_id'
    form_with_inline_formsets = ReplicateDisplayWithInlineMetadata

class ReplicateUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'replicate_id'
    form_with_inline_formsets = ReplicateWithInlineMetadata
    def get_bs_form_opts(self):
        return {
            'submit_text': 'Save Replicate'
        }


class ProtocolList(ListSortingView):
    model = BiologicalReplicateProtocol
    allowed_sort_orders = '__all__'
    grid_fields = ['name', 'description', 'citation']
    def get_heading(self):
        return "Protocol List"
    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('protocol_detail', kwargs={'protocol_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('protocol_update', kwargs={'protocol_id': obj.pk})
            ))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)


class ProtocolStepList(ListSortingView):
    model = ProtocolStep
    allowed_sort_orders = '__all__'
    grid_fields = ['name', 'method']
    def get_heading(self):
        return "Protocol Step List"
    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('protocol_step_detail', kwargs={'protocol_step_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('protocol_step_update', kwargs={'protocol_step_id': obj.pk})
            ))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)



class ProtocolDetail(InlineDetailView):
    pk_url_kwarg = 'protocol_id'
    form_with_inline_formsets = ProtocolDisplayWithInlineSteps

class ProtocolCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'protocol_id'
    form_with_inline_formsets = ProtocolWithInlineSteps
    def get_heading(self):
        return "Create New Protocol"
    def get_bs_form_opts(self):
        return {
            'title': 'Create Protocol',
            'submit_text': 'Save Protocol',
            'inline_title': 'Protocol Steps'
        }

    def get_success_url(self):
        return reverse('protocol_detail', kwargs={'protocol_id': self.object.pk})

class ProtocolUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'protocol_id'
    form_with_inline_formsets = ProtocolWithInlineSteps
    def get_bs_form_opts(self):
        return {
            'title': 'Update Protocol',
            'submit_text': 'Save Protocol',
        }

    def get_success_url(self):
        return reverse('protocol_detail', kwargs={'protocol_id': self.object.pk})


class ProtocolStepDetail(InlineDetailView):
    pk_url_kwarg = 'protocol_step_id'
    form_with_inline_formsets = ProtocolStepDisplayWithInlineParameters

class ProtocolStepCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'protocol_step_id'
    form_with_inline_formsets = ProtocolStepWithInlineParameters
    def get_heading(self):
        return "Create New Protocol Step"
    def get_bs_form_opts(self):
        return {
                'title': 'Create Protocol Step',
                'submit_text': 'Save Protocol Step'
                }

    def get_success_url(self):
        return reverse('protocol_step_detail', kwargs={'protocol_step_id': self.object.pk})

class ProtocolStepUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'protocol_step_id'
    form_with_inline_formsets = ProtocolStepWithInlineParameters
    def get_bs_form_opts(self):
        return {
                'class': 'protocolstep',
                'title': 'Update Protocol Step',
                'submit_text': 'Save Protocol Step'
                }

    def get_success_url(self):
        return reverse('protocol_step_detail', kwargs={'protocol_step_id': self.object.pk})

class PipelineResultList(ListSortingView):
    model = PipelineResult
    allowed_sort_orders = '__all__'
    grid_fields = ['input_file', 'source_software', 'result_type', 'replicates', ['computational_pipelines', 'pipeline_step']]
    def get_heading(self):
        return "Pipeline Result List"

    def get_replicates_text(self, obj):
        return "Number matched: %d" % (len(obj.replicates.all()),)


    def get_file_links(self, obj):
        print("the function was called")
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
        if field == 'replicates':
            return self.get_replicates_text(obj)
        elif field == 'input_file':
            links = self.get_file_links(obj)
            return mark_safe(''.join(links))
            #return self.get_file_name(obj)
        else:
            return super().get_display_value(obj, field)

class PipelineList(ListSortingView):
    model = ComputationalPipeline
    allowed_sort_orders = '__all__'
    grid_fields = ['name']
    def get_heading(self):
        return "Pipeline List"
    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('pipeline_detail', kwargs={'pipeline_id': obj.pk}),
            obj.name
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('pipeline_update', kwargs={'pipeline_id': obj.pk})
            ))
        return links

    def get_display_value(self, obj, field):
        if field == 'name':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)


class PipelineStepList(ListSortingView):
    model = PipelineStep
    allowed_sort_orders = '__all__'
    grid_fields = ['method', 'action']
    def get_heading(self):
        return "Pipeline Step List"
    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('pipeline_step_detail', kwargs={'pipeline_step_id': obj.pk}),
            obj.method
        )]
        # is_authenticated is not callable in Django 2.0.
        if self.request.user.is_authenticated:
            links.append(format_html(
                ' (<a href="{}"><span class="iconui iconui-edit"></span></a>)',
                reverse('pipeline_step_update', kwargs={'pipeline_step_id': obj.pk})
            ))
        return links

    def get_display_value(self, obj, field):
        if field == 'method':
            links = self.get_name_links(obj)
            return mark_safe(''.join(links))
        else:
            return super().get_display_value(obj, field)

class PipelineDetail(InlineDetailView):
    pk_url_kwarg = 'pipeline_id'
    form_with_inline_formsets = PipelineDisplayWithInlineSteps

class PipelineCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'pipeline_id'
    form_with_inline_formsets = PipelineWithInlineSteps
    def get_heading(self):
        return "Create New Pipeline"
    def get_bs_form_opts(self):
        return {
            'title': 'Create Pipeline',
            'submit_text': 'Save Pipeline',
            'inline_title': 'Pipeline Steps'
        }

    def get_success_url(self):
        return reverse('pipeline_detail', kwargs={'pipeline_id': self.object.pk})

class PipelineUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'pipeline_id'
    form_with_inline_formsets = PipelineWithInlineSteps
    def get_bs_form_opts(self):
        return {
            'title': 'Update Pipeline',
            'submit_text': 'Save Pipeline',
        }

    def get_success_url(self):
        return reverse('pipeline_detail', kwargs={'pipeline_id': self.object.pk})

class PipelineResultDetail(InlineDetailView):
    pk_url_kwargs = 'pipeline_result_id'

class PipelineStepDetail(InlineDetailView):
    pk_url_kwarg = 'pipeline_step_id'
    form_with_inline_formsets = PipelineStepDisplayWithInlineParameters

class PipelineStepCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'pipeline_step_id'
    form_with_inline_formsets = PipelineStepWithInlineParameters
    def get_heading(self):
        return "Create New Pipeline Step"
    def get_bs_form_opts(self):
        return {
                'title': 'Create Pipeline Step',
                'submit_text': 'Save Pipeline Step'
                }

    def get_success_url(self):
        return reverse('pipeline_step_detail', kwargs={'pipeline_step_id': self.object.pk})

class PipelineStepUpdate(BsTabsMixin, InlineCrudView):
    format_view_title = True
    pk_url_kwarg = 'pipeline_step_id'
    form_with_inline_formsets = PipelineStepWithInlineParameters
    def get_bs_form_opts(self):
        return {
                'class': 'pipelinestep',
                'title': 'Update Pipeline Step',
                'submit_text': 'Save Pipeline Step'
                }

    def get_success_url(self):
        return reverse('pipeline_step_detail', kwargs={'pipeline_step_id': self.object.pk})



###############################################################################
### SEARCH AND QUERY BASED VIEWS                                            ####
###############################################################################

#A simple function based view to GET the search bar form
def search(request):
    ##MODEL INFO:::
    ## (logic_model_type, db_model_type, user_facing_model_string)
    model_types= [('investigation', Investigation, 'Investigations'),
                  ('sample', Sample, 'Samples'),
                  ('sampleMetadata', SampleMetadata, 'Sample Metadata'),
                  ('biologicalReplicate', BiologicalReplicate, 'Biological Replicates'),
                  ('biologicalReplicateMetadata', BiologicalReplicateMetadata, 'Biological Replicate Metadata'),
                  ('protocol', BiologicalReplicateProtocol, 'Biological Replicate Protocols'),
                  ('pipeline', ComputationalPipeline, 'Computational Pipeline'),
                  ('pipelineStep', PipelineStep, 'Computational Pipeline Step' )]

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
    print("Min selected: ", min_selected)

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
            qs = qs.filter(key=meta)
            if min_selected and max_selected:
                qs = qs.annotate(num_val=Cast('value', models.FloatField())).filter(
                    num_val__lte=max_selected).filter(num_val__gte=min_selected)

        if q:
            qs = qs.filter(search_vector = query)
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
        #this_qs.annotate(n=models.Count('pk')) #why is this here? delete bu August if no bugs come up.

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
    value_range = None
    if selected['type'] == 'sampleMetadata':
        metadata = SampleMetadata.objects.order_by('key').distinct('key')
        if meta:
            value_range = {
                'min': SampleMetadata.objects.filter(key=meta).aggregate(models.Min('value'))['value__min'],
                'max': SampleMetadata.objects.filter(key=meta).aggregate(models.Max('value'))['value__max'],
            }

    elif selected['type'] == 'biologicalReplicateMetadata':
        metadata = BiologicalReplicateMetadata.objects.order_by('key').distinct('key')
        if meta:
            value_range = {
                'min': BiologicalReplicateMetadata.objects.filter(key=meta).aggregate(models.Min('value'))['value__min'],
                'max': BiologicalReplicateMetadata.objects.filter(key=meta).aggregate(models.Max('value'))['value__max'],
            }

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
        'title':title,
        'results':results,
        'page_total': paginator.count,
        'page': page,
        'type_counts': type_counts,
        'selected': selected,
        'type': selected_type,
        'metadata':metadata,
        'meta': meta,
        'value_range': value_range,
        'min_value': min_selected,
        'max_value': max_selected,
        #'value_form': value_form,
            #'search_page': "active",
    })

###############################################################################
###            ANALYSIS VIEWS                                             #####
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
        success_url = '/analyze/'

        def form_invalid(self, form):
            print("form invalid for some reason")
            print(form.errors)
            return super().form_invalid(form)

        def form_valid(self, form):
            req = self.request.POST
            html = barchart_html(req['agg_choice'], req['invField'], req['modelField'],
                                req['metaValueField'])
            return render(self.request, 'analyze/plot_aggregate.htm', {'graph':html})

#ajax view for populating metaValue Field
def ajax_aggregates_meta_view(request):
    inv_id = request.GET.get('inv_id')
    model_choice = request.GET.get('type')
    #get investigation specific meta data.
    #E.g. Inv -> Samples -> SampleMetadata
    #     Inv -> Reps -> BiologicalReplicateMetadata
    qs = None
    type = None

    if model_choice == "1": #Samples
        print("yes")
        qs = SampleMetadata.objects.filter(
            sample__in = Sample.objects.filter(
            investigation = inv_id
            )).order_by('key').distinct('key')
        type = "sample"
    elif model_choice == "2": #Bio Replicates
        qs = BiologicalReplicateMetadata.objects.filter(
            biological_replicate__in = (BiologicalReplicate.objects.filter(
            sample__in = Sample.objects.filter(investigation=inv_id)
            ))).order_by('key').distinct('key')
        type = "replicate"
#    elif model_choice == '3': #Computational something or other
    return render (request, 'analyze/ajax_model_options.htm', {'type': type, 'qs':qs,})


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
