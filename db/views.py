from django.shortcuts import render, redirect
from .forms import CreateInvestigationForm, ConfirmSampleForm
from django.shortcuts import render
from django.views import View
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.messages import get_messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils.html import format_html, mark_safe

from django_jinja_knockout.views import (
        BsTabsMixin, ListSortingView, InlineCreateView, InlineCrudView, InlineDetailView
)

import django_tables2 as tables
import io

from .formatters import format_sample_metadata, guess_filetype
from .models import (
        Sample, SampleMetadata, Investigation, BiologicalReplicateProtocol,
        ProtocolStep, UploadInputFile
)

from .forms import (
    InvestigationDisplayWithInlineSamples, InvestigationWithInlineSamples,
    ProtocolForm, ProtocolDisplayWithInlineSteps, 
    ProtocolStepWithInlineParameters, ProtocolStepDisplayWithInlineParameters,
    ProtocolWithInlineSteps, SampleDisplayWithInlineMetadata,
    SampleWithInlineMetadata, UploadForm, UserWithInlineUploads
)

import pandas as pd
import numpy as np

'''
DJK INVESTIGATIONS
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
#        return reverse('upload_detail', kwargs={'upload_id': self.object.pk})

#class UploadDetail(InlineDetailView)


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

'''
INVESTIGATIONS
'''


@login_required()
def add_investigations_view(request):
    form = CreateInvestigationForm(request.POST or None)
    action = "Create Investigation"
    if request.method == 'POST' and form.is_valid:
        # todo handle is investigation exists. -> Create or search:
        investigation = form.save()
        request.session['investigation_name'] = investigation.name
        return redirect('landing')
    context = {'form': form, 'action': action}
    return render(request, 'db/add_investigation.html', context)

#def investigation_search(request):
#    # todo full text search on investigation table
#    query = request.GET.get('q')
#    print(query)
#    return render(request, 'db/search_investigation.html')

def list_of_investigations():
    #todo, list of 20 or so most recent investigations
    pass


'''
SAMPLES
'''


@login_required()
def add_sample_view(request):
    # todo make html
    action = 'Add Samples'
    context = {'action': action}
    return render(request, 'db/add_sample.html', context)

@login_required()
def confirm_samples_view(request):
    new_names = []
    form = None
    if 'confirm_samples' in request.session: 
        new_names = request.session['confirm_samples'].split(",")
        if request.method == 'POST':
            form = ConfirmSampleForm(new_names, request)
            if form.is_valid():
                print("SAVING")
                del request.session['confirm_samples']
                del request.session['confirm_visible']
                del request.session['confirm_type']
                return redirect('landing')
        else:
            #create an initial form
            form = ConfirmSampleForm(new_names)
    else:
        #Return some "nothing to confirm" screen?
        pass
    action = 'Confirm Samples'
    context = {'action': action,
               'form': form}
    return render(request, 'db/confirm_samples.html', context)


'''
WETLAB
'''


@login_required()
def add_wetlab_view(request):
    # todo make html
    action = 'Add Wetlab Data'
    context = {'action': action}
    return render(request, 'db/add_wetlab.html', context)


'''
BIOLOGICAL PROTOCOL
'''

@login_required()
def add_biological_protocol_view(request):
    #  todo make html
    action = 'Add Biological Protocol Data'
    context = {'action': action}
    return render(request, 'db/add_biological_protocol.html', context)


'''
PIPELINERESULTS
'''


def add_pipeline_results_view(request):
    # todo make html
    action = 'Add Pipeline Results'
    context = {'action': action}
    return render(request, 'db/add_pipeline_results.html', context)

#def search(request):
#    return render(request, 'db/search.html', context={})


#def browse(request):
#    return render(request, 'db/browse.html', context={})

@login_required()
def upload_view(request):
#    create_investigation_form = CreateInvestigationForm(request.POST or None)
    form = UploadTestForm(request.POST, request.FILES)
    if (request.method == 'POST') & form.is_valid():
        #If we've already been here, confirm_visible will be in the session
        #And that means a POST wants us to shuttle the upload data to a
        #confirmation page, depending on upload type
        if 'confirm_visible' in request.session:
            if 'confirm_type' not in request.session:
                #This shouldn't happen except for farked up sessions, but this
                #should jog the state back if it does
                del request.session['confirm_visible']
                del request.session['sample_names']
                return
            else:
#                if request.session['confirm_type'] == 'sample_table':
#                    return redirect("db:confirm_samples")
#                else:
                    return redirect('landing')
        # File processing code
        # Guess what it is, then rewind the inmemoryfile
        if 'upload_file' in request.FILES:
            guessed_type = guess_filetype(request.FILES['upload_file'])
            print(guessed_type)
            request.FILES['upload_file'].seek(0)    
            if guessed_type == 'sample_table':
                table = format_sample_metadata(request.FILES['upload_file'])
                new_samples = []
                previously_registered = []
                for sample_id in np.unique(table['sample-id']):
                    sc = Sample.objects.filter(name__exact=sample_id)
                    if sc.count() > 0:
                        previously_registered.append(sample_id)
                    else:
                        new_samples.append(sample_id)
                context = {'confirm_visible': True,
                        'confirm_type': guessed_type,
                        'num_new_samples': len(new_samples),
                        'num_registered_samples': len(previously_registered)}
                request.session['confirm_samples'] = ','.join(new_samples)
                request.session['confirm_visible'] = True
                request.session['confirm_type'] = guessed_type    
            else:
                context = {'form': form, 'confirm_visible': False}#'create_investigation_form': create_investigation_form}
        else:
            context = {'form': form, 'confirm_visible': False}#, 'create_investigation_form': create_investigation_form}
        return JsonResponse(context)
    else:
        context = {'form': form, 'confirm_visible': False}#, 'create_investigation_form': create_investigation_form}
        return render(request, 'db/upload.html', context)
