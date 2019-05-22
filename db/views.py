from django.shortcuts import render, redirect
from .forms import CreateInvestigationForm, ConfirmSampleForm
from django.shortcuts import render
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

from django.core.paginator import(
    Paginator,
    EmptyPage,
    PageNotAnInteger,
)
from django_jinja_knockout.views import (
        BsTabsMixin, ListSortingView, InlineCreateView, InlineCrudView, InlineDetailView,
        FormDetailView
)

import django_tables2 as tables
import io

from .formatters import format_sample_metadata, guess_filetype
from .models import (
        Sample, SampleMetadata, Investigation, BiologicalReplicateProtocol,
        ProtocolStep, UploadInputFile, load_mixed_objects
)

from .forms import (
    InvestigationDisplayWithInlineSamples, InvestigationWithInlineSamples,
    ProtocolForm, ProtocolDisplayWithInlineSteps,
    ProtocolStepWithInlineParameters, ProtocolStepDisplayWithInlineParameters,
    ProtocolWithInlineSteps, SampleDisplayWithInlineMetadata,
    SampleWithInlineMetadata, UploadForm, UserWithInlineUploads, UploadInputFileDisplayForm,
    UploadInputFileDisplayWithInlineErrors
)

import pandas as pd
import numpy as np

###Stuff for searching
from django.contrib.postgres.search import SearchQuery
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.search import SearchRank
from django.db.models import F

'''
Class-based Django-Jinja-Knockout views
'''

class UploadCreate(BsTabsMixin, InlineCreateView):
    format_view_title = True
    pk_url_kwarg = 'userprofile_id'
    form_with_inline_formsets = UserWithInlineUploads
    def get_bs_form_opts(self):
        return {
                'title': 'Upload Files',
                'submit_text': 'Upload',
                }

#    def get_success_url(self):
#        return reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': self.object.pk})

class UploadList(ListSortingView):
    model = UploadInputFile
    allowed_sort_orders = '__all__'
    grid_fields = ['upload_file', 'upload_status','userprofile']

    def get_heading(self):
        return "Upload List"

    def get_name_links(self, obj):
        links = [format_html(
            '<a href="{}">{}</a>',
            reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': obj.pk}),
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
    pk_url_kwarg = 'uploadinputfile_id'
    form_with_inline_formsets = UploadInputFileDisplayWithInlineErrors
    format_view_title = True
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
            'submit_text': "Save Investigation"
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

class PipelineList(ListSortingView):
    pass

class PipelineStepList(ListSortingView):
    pass
###############################################################################
### SEARCH AND QUERY BASED VIEWS                                            ####
###############################################################################

#The url for this should pass a param, i.e. path('search/<query>/')
"""
It seems a function based view might be more appropriate! commenting this out
for now so that I dont lose it if things go south.
##

class SearchResultList(ListView):
    template_name = 'search_results.htm'

    #Can I access the GET variables here????

    ############################################################################
    ### get_queryset() queries the database using search vectors. Each model ###
    ### class has been given a search vector field. The search vector field  ###
    ### essentially indexes searching on each of the models' fields. This    ###
    ### allows fast search and union of objects with different numbers of    ###
    ### fields: We can union the queryset on pk, though the results will be  ###
    ### based on search against the search vector.                           ###
    ############################################################################
    def get_queryset(self):
        query = self.kwargs['query']
        rank_annotation = SearchRank(F('search_vector'), query)
        model_types= [('investigation', Investigation), ('sample', Sample),
                      ('sampleMetadata', SampleMetadata)]
        #Make an empty QuerySet. arbitrarily use Investigation as the model.
        results = Investigation.objects.annotate(
            type=models.Value('empty', output_field=models.CharField()),
            rank=rank_annotation
        ).values('pk','type', 'rank').none()

        #Now, more models can be added simply by adding to the model_types list.
        for model_type in model_types:
                results = results.union(model_type[1].objects.annotate(
                        rank=rank_annotation,
                        type = models.Value(model_type[0],output_field=models.CharField())
                ).filter(search_vector=query).values('pk','type','rank'))


        #results is now a QuerySet: A list of dicts containing primary key,
        #search rank as a value from 0.0-1.0,  and type. This list can be used
        #to load the model objects from the database.
        return results

"""
#A simple function based view to GET the search bar form
def search(request):
    ##MODEL INFO:::
    model_types= [('investigation', Investigation), ('sample', Sample),
                  ('sampleMetadata', SampleMetadata),
                  ('protocol', BiologicalReplicateProtocol)]

    q = request.GET.get('q', '').strip() #user input from search bar
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

    for type_name, model_type in model_types:
        this_qs = make_queryset(model_type, type_name)
        #TODO add counts for each type here.
        #type_count = this_qs.count()
        qs = qs.union(this_qs.values(*values))

    if q:
        qs = qs.order_by('-rank')

    #use a pagintator.
    paginator = Paginator(qs, 20) #20 results per page? maybe 20 pages.
    page_number = request.GET.get('page') or '1'
    try:
        page = paginator.page(page_number)
        #will pass page to the context.
    except PageNotAnInteger:
        raise Http404
    except EmptyPage:
        raise Http404

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

    return render(request, 'search_results.htm',{
        'q':q,
        'title':title,
        'results':results,
        'page_total': paginator.count,
        'page': page,
    })

#probably have to do something along the lines of
# A template with extensive conditionals.
