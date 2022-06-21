from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.db import models
from ..models import (
    Investigation,
    Process, Step, Analysis,
    Result,
    Sample, Feature,
    Value, Parameter, Matrix,
    DataSignature,
    UploadFile, UserProfile, UploadMessage
)
from ..models.object import Object

from django.forms import formset_factory, ModelForm

#Stuff for custom FieldSetForm
from django.forms.models import ModelFormOptions

from dal import autocomplete


class FileFieldForm(forms.Form):
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

class UploadForm(ModelForm):
    class Meta:
        model = UploadFile
        fields = ['upload_file']


################ Upload Forms
class ArtifactUploadForm(ModelForm):
    analysis = forms.ModelChoiceField(queryset=Analysis.objects.all(), empty_label="Select an Analysis")
    class Meta:
        model = UploadFile
        #exclude = ('userprofile', )
        fields = ('analysis', 'upload_file',)
    def __init__(self, *args, **kwargs):
        self.userprofile = kwargs.pop('userprofile')
        super(ArtifactUploadForm, self).__init__(*args, **kwargs)

class SpreadsheetUploadForm(ModelForm):
    class Meta:
        model = UploadFile
        #exclude = ('userprofile', )
        fields = ('upload_file',)
    def __init__(self, *args, **kwargs):
        self.userprofile = kwargs.pop('userprofile')
        super(SpreadsheetUploadForm, self).__init__(*args, **kwargs)

class SimpleMetadataUploadForm(ModelForm):
    overwrite = forms.BooleanField(required=False)
    class Meta:
        model=UploadFile
        fields = ('upload_file', 'overwrite',)
    def __init__(self, *args, **kwargs):
        self.userprofile = kwargs.pop('userprofile')
        super(SimpleMetadataUploadForm, self).__init__(*args, **kwargs)

##########################


#This form used only for display purposes
class UploadFileDisplayForm(ModelForm):
        class Meta:
            model=UploadFile
            fields = '__all__'

class ErrorDisplayForm(ModelForm):
    class Meta:
        model = UploadMessage
        fields = '__all__'

