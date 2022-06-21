# ----------------------------------------------------------------------------
# path: quorem/db/views/upload_views.py
# authors: Mike Hall
# modified: 2022-06-21
# description: This file contains all views that are for upload functions.
# ----------------------------------------------------------------------------

from collections import OrderedDict
import string
import time
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils.html import format_html, mark_safe
from django.http import HttpResponseRedirect

from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from celery import current_app

from ..models import *
from ..forms import *
from .generic_views import reverse

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

