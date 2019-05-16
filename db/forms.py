from django import forms
from django.conf import settings
from django.db import models
from django.forms.widgets import HiddenInput
from django.forms.utils import flatatt
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    BiologicalReplicate, BiologicalReplicateProtocol, ComputationalPipeline,
    Investigation, ProtocolStep, ProtocolStepParameter, Sample, SampleMetadata,
    UploadInputFile, UserProfile
)

from django_jinja_knockout.forms import (
    DisplayModelMetaclass, FormWithInlineFormsets, RendererModelForm,
    ko_inlineformset_factory, ko_generic_inlineformset_factory, WidgetInstancesMixin
)
from django_jinja_knockout.widgets import ForeignKeyGridWidget, DisplayText


'''
Django-Jinja-Knockout Forms
'''

#Base Forms and Display Forms

class UserProfileForm(RendererModelForm):
    class Meta:
        model = UserProfile
        fields = '__all__'

TEST_CHOICES = (
            ('1', 'Choice 1'),
            ('2', 'Choice 2'),
            ('3', 'Choice 3'),
)


class UploadForm(RendererModelForm):
    class Meta:
        model = UploadInputFile
        fields = ['userprofile', 'upload_file']

UserUploadFormset = ko_inlineformset_factory(UserProfile,
                                             UploadInputFile,
                                             form=UploadForm,
                                             extra=0,
                                             min_num=1)


class UserWithInlineUploads(FormWithInlineFormsets):
    FormClass = UserProfileForm
    FormsetClasses = [UserUploadFormset]
    def get_formset_inline_title(self, formset):
        return "User Uploads"

class InvestigationForm(RendererModelForm):
    class Meta:
        model = Investigation
        fields = '__all__'

class InvestigationDisplayForm(RendererModelForm,
                               metaclass=DisplayModelMetaclass):
    class Meta:
        model = Investigation
        fields = '__all__'


class NameLabelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s" % (obj.name,)

class SampleForm(RendererModelForm):
    investigation = NameLabelChoiceField(queryset = Investigation.objects.all())
    class Meta:
        model = Sample
        fields = '__all__'

class SampleDisplayForm(WidgetInstancesMixin, RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        def get_name(self, value):
            return format_html('<a{}>{}</a>', flatatt({'href': reverse('sample_detail', kwargs={'sample_id': self.instance.pk})}), self.instance.name)
        def get_investigation(self, value):
            return format_html('<a{}>{}</a>', flatatt({'href': reverse('investigation_detail', kwargs={'investigation_id': self.instance.investigation.pk})}), self.instance.investigation.name)

        model = Sample
        fields = '__all__'
        widgets = {'name': DisplayText(get_text_method=get_name),
                   'investigation': DisplayText(get_text_method=get_investigation)}

class ReplicateForm(RendererModelForm):
    class Meta:
        model = BiologicalReplicate
        fields = '__all__'

class ReplicateDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = BiologicalReplicate
        fields = '__all__'

class SampleMetadataForm(RendererModelForm):
    class Meta:
        model = SampleMetadata
        fields = '__all__'

class SampleMetadataDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = SampleMetadata
        fields = '__all__'

class ProtocolForm(RendererModelForm):
    class Meta:
        model = BiologicalReplicateProtocol
        fields = '__all__'

class ProtocolDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = BiologicalReplicateProtocol
        fields = '__all__'

class PipelineForm(RendererModelForm):
    class Meta:
        model = ComputationalPipeline
        fields = '__all__'

class PipelineDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = ComputationalPipeline
        fields = '__all__'

class ProtocolStepForm(RendererModelForm):
    protocolstep = NameLabelChoiceField(queryset=ProtocolStep.objects.all())
    protocolstep.label = "Protocol Step"
    class Meta:
        model = ProtocolStep
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super(ProtocolStepForm, self).__init__(*args, **kwargs)
        if 'biological_replicate_protocols' in self.fields:
            self.fields.pop('biological_replicate_protocols')
            self.fields.pop('protocolstep')

class ProtocolStepDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = ProtocolStep
        fields = '__all__'

class ProtocolStepParameterForm(RendererModelForm):
    class Meta:
        model = ProtocolStepParameter
        fields = '__all__'

class ProtocolStepParameterDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = ProtocolStepParameter
        fields = '__all__'


# Inline/Compound Forms

InvestigationSampleFormset = ko_inlineformset_factory(Investigation,
                                                      Sample,
                                                      form=SampleForm,
                                                      extra=0,
                                                      min_num=0)
InvestigationDisplaySampleFormset = ko_inlineformset_factory(
                                                 Investigation,
                                                 Sample,
                                                 form=SampleDisplayForm)

class InvestigationWithInlineSamples(FormWithInlineFormsets):
    FormClass = InvestigationForm
    FormsetClasses = [InvestigationSampleFormset]
    def get_formset_inline_title(self, formset):
        return "Sample"


class InvestigationDisplayWithInlineSamples(FormWithInlineFormsets):
     FormClass = InvestigationDisplayForm
     FormsetClasses = [InvestigationDisplaySampleFormset]
     def get_formset_inline_title(self, formset):
         return "Samples"

SampleDisplayMetadataFormset = ko_inlineformset_factory(Sample,
                                                 SampleMetadata,
                                                 form=SampleMetadataDisplayForm)

SampleDisplayReplicateFormset = ko_inlineformset_factory(Sample,
                                                      BiologicalReplicate,
                                                      form=ReplicateDisplayForm)

SampleMetadataFormset = ko_inlineformset_factory(Sample, SampleMetadata,
                                                 form=SampleMetadataForm,
                                                 extra=0,
                                                 min_num=0)

SampleReplicateFormset = ko_inlineformset_factory(Sample, BiologicalReplicate,
                                                  form=ReplicateForm,
                                                  extra=0, min_num=0)

class SampleWithInlineMetadata(FormWithInlineFormsets):
    FormClass = SampleForm
    FormsetClasses = [SampleMetadataFormset]
    def get_formset_inline_title(self, formset):
        return "Sample Metadata"

class SampleDisplayWithInlineMetadata(FormWithInlineFormsets):
    FormClass = SampleDisplayForm
    FormsetClasses = [SampleDisplayReplicateFormset, \
                      SampleDisplayMetadataFormset]
    def get_formset_inline_title(self, formset):
        return "Sample Metadata"

ProtocolStepDisplayFormset = ko_inlineformset_factory(BiologicalReplicateProtocol,
                                                      ProtocolStep.biological_replicate_protocols.through,
                                                      form=ProtocolStepDisplayForm)

ProtocolStepFormset = ko_inlineformset_factory(BiologicalReplicateProtocol,
                                               ProtocolStep.biological_replicate_protocols.through,
                                               form=ProtocolStepForm,
                                               extra=0, min_num=0)

class ProtocolDisplayWithInlineSteps(FormWithInlineFormsets):
    FormClass = ProtocolDisplayForm
    FormsetClasses = [ProtocolStepDisplayFormset]
    def get_formset_inline_title(self, formset):
        return "Protocol Step"

class ProtocolWithInlineSteps(FormWithInlineFormsets):
    FormClass = ProtocolForm
    FormsetClasses = [ProtocolStepFormset]
    def get_formset_inline_title(self, formset):
        return "Protocol Steps"

ProtocolStepParameterDisplayFormset = ko_inlineformset_factory(ProtocolStep,
                                                      ProtocolStepParameter,
                                                      form = ProtocolStepParameterDisplayForm)

ProtocolStepParameterFormset = ko_inlineformset_factory(ProtocolStep,
                                                        ProtocolStepParameter,
                                                        form = ProtocolStepParameterForm,
                                                        extra=0, min_num=0)

class ProtocolStepWithInlineParameters(FormWithInlineFormsets):
    FormClass = ProtocolStepForm
    FormsetClasses = [ProtocolStepParameterFormset]
    def get_formset_inline_title(self, formset):
        return "Protocol Step Parameter"

class ProtocolStepDisplayWithInlineParameters(FormWithInlineFormsets):
    FormClass = ProtocolStepDisplayForm
    FormsetClasses = [ProtocolStepParameterDisplayFormset]
    def get_formset_inline_title(self, formset):
        return "Protocol Step Parameters"

''' Django Forms '''

class CreateInvestigationForm(forms.ModelForm):
    class Meta:
        model = Investigation
        fields = '__all__'

class ConfirmSampleForm(forms.Form):
    """ A manually generated form that outputs BooleanFields for
    each new sample that is being added, and asks the user to confirm that
    they wish them to be added """
    def __init__(self, new_samples, request=None,
                       *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        for i in range(len(new_samples)):
            field_name = 'new_sample_%d' % (i,)
            self.fields[field_name] = forms.BooleanField(label=new_samples[i], required=False)
            self.initial[field_name] = True

    def clean(self):
        samples = set()
        i = 0
        field_name = 'new_sample_%d' % (i,)
        while self.cleaned_data.get(field_name):
           sample = self.cleaned_data[field_name]
           samples.add(sample)
           i += 1
           field_name = 'new_sample_%d' % (i,)
        self.cleaned_data["samples"] = samples

    def save(self):
        #TODO: get investigation and assign it properly here
        vsi = self.instance
        vsi.new_sample_set.all().delete()
        for sample in self.cleaned_data["samples"]:
           Sample.objects.create(name=sample, investigation=0)

    def get_sample_checklist(self):
        for field_name in self.fields:
            if field_name.startswith('new_sample_'):
                yield self[field_name]
