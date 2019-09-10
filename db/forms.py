from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Replicate, Process,
    Step, Result, Value,
    Investigation, Step, Sample,
    UploadInputFile, UserProfile, ErrorMessage
)

from django_jinja_knockout.forms import (
    DisplayModelMetaclass, FormWithInlineFormsets, RendererModelForm,
    ko_inlineformset_factory, ko_generic_inlineformset_factory, WidgetInstancesMixin,
    BootstrapModelForm
)
from django_jinja_knockout.widgets import ForeignKeyGridWidget, DisplayText

from django.forms import inlineformset_factory, ModelForm

#Stuff for custom FieldSetForm
from django.forms.models import ModelFormOptions


"""
Custom Form Classes
"""
#ModelFormOption config to allow FieldSetForm
_old_init = ModelFormOptions.__init__
def _new_init(self, options=None):
    _old_init(self, options)
    self.fieldsets = getattr(options, 'fieldsets', None)
ModelFormOptions.__init__ = _new_init

##Fieldset class will allow multi-part forms to be Rendered  in the way
# you might expect rather than having to use sessions and third party libs.
class Fieldset(object):
    def __init__(self, form, title, description, fields, classes):
        self.form = form
        self.title = title
        self.description = description
        self.fields = fields
        self.classes = classes
    #iter allows intuitive template rendering
    def __iter__(self):
        for field in self.fields:
            yield field

##Add a fieldsets() method to BaseForm to allow forms to have fieldsets.
def fieldsets(self):
    meta = getattr(self, '_meta', None)
    if not meta:
        meta = getattr(self, 'Meta', None)
    if not meta or not meta.fieldsets:
        return
    for name, desc, data in meta.fieldsets:
        yield Fieldset(
            form=self,
            title=name,
            description=desc,
            fields=(self[f] for f in data.get('fields',())),
            classes=data.get('classes', '')
        )

forms.BaseForm.fieldsets = fieldsets

'''
Django-Jinja-Knockout Forms
'''

#Base Forms and Display Forms

class UserProfileForm(RendererModelForm):
    #ModelForm will auto-generate fields which dont already exist
    #Therefore, creating fields prevents auto-generation.
    class Meta:
        model = UserProfile
        fields = ['user']



class UploadForm(WidgetInstancesMixin, BootstrapModelForm):
    class Meta:
        model = UploadInputFile
        fields = ['upload_file']

UserUploadFormset = ko_inlineformset_factory(UserProfile,
                                             UploadInputFile,
                                             form=UploadForm,
                                             extra=0,
                                             min_num=1)

################Experiment
class NewUploadForm(ModelForm):
    class Meta:
        model = UploadInputFile
        #exclude = ('userprofile', )
        fields = ('upload_file',)
    def __init__(self, *args, **kwargs):
        self.userprofile = kwargs.pop('userprofile')
        super(NewUploadForm, self).__init__(*args, **kwargs)


##########################


#This form used only for display purposes
class UploadInputFileDisplayForm(WidgetInstancesMixin,
                                RendererModelForm,
                                metaclass=DisplayModelMetaclass):
        class Meta:
            model=UploadInputFile
            fields = '__all__'

class ErrorDisplayForm(WidgetInstancesMixin, RendererModelForm,
                        metaclass=DisplayModelMetaclass):
    class Meta:
        model = ErrorMessage
        fields = '__all__'



UploadInputFileDisplayErrorFormset = ko_inlineformset_factory(
                                                UploadInputFile,
                                                ErrorMessage,
                                                form=ErrorDisplayForm,
                                                extra=0,
                                                min_num=0,
                                                can_delete=False)

class UploadInputFileDisplayWithInlineErrors(FormWithInlineFormsets):
    FormClass = UploadInputFileDisplayForm
    FormsetClasses =[UploadInputFileDisplayErrorFormset]
    def get_formset_inline_title(self, formset):
        return "Error Messages"

class UserWithInlineUploads(FormWithInlineFormsets):
    FormClass = UserProfileForm
    FormsetClasses = [UserUploadFormset]
    def get_formset_inline_title(self, formset):
        return "User Uploads"

class NameLabelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s" % (obj.name,)

#### Investigation Forms

class InvestigationForm(RendererModelForm):
    class Meta:
        model = Investigation
        exclude = ['search_vector', 'values']

class InvestigationDisplayForm(RendererModelForm,
                               metaclass=DisplayModelMetaclass):
    class Meta:
        model = Investigation
        exclude = ['search_vector']

class SampleForm(RendererModelForm):
    investigation = NameLabelChoiceField(queryset = Investigation.objects.all())
    class Meta:
        model = Sample
        exclude = ['search_vector']

class SampleDisplayForm(WidgetInstancesMixin, RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        def get_name(self, value):
            return format_html('<a{}>{}</a>', flatatt({'href': reverse('sample_detail', kwargs={'sample_id': self.instance.pk})}), self.instance.name)
        def get_investigation(self, value):
            return format_html('<a{}>{}</a>', flatatt({'href': reverse('investigation_detail', kwargs={'investigation_id': self.instance.investigation.pk})}), self.instance.investigation.name)

        model = Sample
        exclude = ['search_vector']
        widgets = {'name': DisplayText(get_text_method=get_name),
                   'investigation': DisplayText(get_text_method=get_investigation)}

class ReplicateForm(RendererModelForm):
    class Meta:
        model = Replicate
        exclude = ['search_vector']

class ReplicateDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = Replicate
        exclude = ['search_vector']

class ProcessForm(RendererModelForm):
    class Meta:
        model = Process
        exclude = ['search_vector']

class ProcessDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = Process
        exclude = ['search_vector']

class StepForm(RendererModelForm):
#    step = NameLabelChoiceField(queryset=Step.objects.all())
#    step.label = "Process Step"
    class Meta:
        model = Step
        exclude = ['search_vector']

class StepDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = Step
        exclude = ['search_vector']

# No ResultForm, we don't need to edit that one manually. Results come in with Upload Files

class ResultDisplayForm(RendererModelForm, metaclass=DisplayModelMetaclass):
    class Meta:
        model = Result
        exclude = ['search_vector']

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

SampleDisplayReplicateFormset = ko_inlineformset_factory(Sample,
                                                      Replicate,
                                                      form=ReplicateDisplayForm)

SampleReplicateFormset = ko_inlineformset_factory(Sample, Replicate,
                                                  form=ReplicateForm,
                                                  extra=0, min_num=0)

StepDisplayFormset = ko_inlineformset_factory(Process,
                                              Step.processes.through,
                                              form=StepDisplayForm)

StepFormset = ko_inlineformset_factory(Process,
                                       Step.processes.through,
                                       form=StepForm,
                                       extra=0, min_num=0)

class ProcessDisplayWithInlineSteps(FormWithInlineFormsets):
    FormClass = ProcessDisplayForm
    FormsetClasses = [StepDisplayFormset]
    def get_formset_inline_title(self, formset):
        return "Process Step"

class ProcessWithInlineSteps(FormWithInlineFormsets):
    FormClass = ProcessForm
    FormsetClasses = [StepFormset]
    def get_formset_inline_title(self, formset):
        return "Process Steps"

##### Search form
class SearchBarForm(forms.Form):
    search = forms.CharField(max_length=100)

##### Fieldset Forms

class AggregatePlotForm(forms.Form):
    AGG_CHOICES = (
        ('C', 'Count'),
        ('U', 'Mean'),
    )
    agg_choice = forms.ChoiceField(choices=AGG_CHOICES)
    #Other Fields, placeholder for now until I figure it out
    field1 = forms.CharField()
    field2 = forms.CharField()
    field3 = forms.CharField()

    class Meta:
        fieldsets = (
        #title, description, Fields
            ('Select an Aggregate Query', 'Select Aggregate', {'fields': ('agg_choice',)}),
            ('Select Dependant and Independant Variables', 'Select Variables', {'fields': ('field1', 'field2')}),
            ('Select Filters for Data', 'Filter Data', {'fields': ('field3',)}),
        )

##### Aggregation Views and utils

# Custom Field Choice for rendering form
class CustomModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        #if type(obj) is SampleMetadata or type(obj) is ReplicateMetadata:
        #    return obj.key
        #else:
            return super().label_from_instance(obj)

#Form for barcharts. Maybe pie charts someday!
class AggregatePlotInvestigation(forms.Form):
    AGG_CHOICES = (
        ('1', 'Count'),
        ('2', 'Mean'),
        ('3', 'Stack'),
    )
    MODEL_CHOICES = (
        ('', '----------'),
        ('1', 'Samples'),
    #    ('2', 'Biological Replicates'),
    #    ('3', 'Computational Pipelines'),

    )
    agg_choice = forms.ChoiceField(widget=forms.RadioSelect, choices=AGG_CHOICES)
    invField = forms.ModelMultipleChoiceField(queryset = Investigation.objects.all(),
                                      label="Select Investigation(s)")
    modelField = forms.ChoiceField(choices = MODEL_CHOICES, label="Select Query Object")
    #metaValueField will be populated by AJAX call to ajax_model_options view
    metaValueField = forms.CharField(widget=forms.SelectMultiple, label="Select X Value")

    class Meta:
        fieldsets = (
            ('Aggregate', 'Select Aggregation Operation', {'fields': ('agg_choice',)}),
            ('Data Choice', 'Select Investigation and Models', {'fields': ('invField', 'modelField',)}),
            ('Filter', 'Select parameters to filter your data', {'fields': ('metaValueField',)}),
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.fields['metaValueField'].queryset = SampleMetadata.objects.order_by('key').distinct('key')
"""
class AggregatePlotStackedForm(forms.Form):
    MODEL_CHOICES = (
        ('', '----------'),
        ('1', 'Samples'),
    #    ('2', 'Biological Replicates'),
    #    ('3', 'Computational Pipelines'),

    )
    invField = forms.ModelMultipleChoiceField(queryset = Investigation.objects.all(),
                                      label="Select Investigation(s)")
    modelField = forms.ChoiceField(choices = MODEL_CHOICES, label="Select Query Object")
    stackedParams = forms.CharField(widget=forms.SelectMultiple, label="Choose stacked values")

    class Meta:
        fieldsets = (
            ('Aggregate', 'Select Aggregation Operation', {'fields': ('agg_choice',)}),
            ('Data Choice', 'Select Investigation and Models', {'fields': ('invField', 'modelField',)}),
            ('Filter', 'Select parameters to filter your data', {'fields': ('stackedParams',)}),
        )
"""
#Form for trendline plotting
class TrendPlotForm(forms.Form):
    MODEL_CHOICES = (
        ('', '----------'),
        ('1', 'Samples'),
    #    ('2', 'Biological Replicates'),
    #    ('3', 'Computational Pipelines'),

    )
    #In each field, define class labels for widgets where field change affects subesqeuent fields.
    #These class labels will have JS event listeneres attached where relevant.
    invField = forms.ModelMultipleChoiceField(queryset = Investigation.objects.all(),
                                      label="Select Investigation(s)")
    x_val_category = forms.ChoiceField(choices = MODEL_CHOICES, label="Select X-value category.", widget=forms.Select(attrs={'class':'x-val'}))
    x_val = forms.CharField(widget=forms.Select, label="Select X Value.")

    y_val_category = forms.ChoiceField(choices = MODEL_CHOICES, label="Select Y-value category.")
    y_val = forms.CharField(widget=forms.Select, label="Select Y Value.")

    operation_choice = forms.ChoiceField(choices = (('1','Scatter'),('2','Contiuous')),
                                        label="Select Plot Type.")

    class Meta:
        fieldsets = (
            ('Choose Investigation(s)', "Select Investigation(s)", {'fields': ('invField',)}),
            ('Choose Dependant Variable', "Select X", {'fields': ('x_val_category', 'x_val',)}),
            ("Choose Independant Variable", "Select Y", {'fields': ('y_val_category', 'y_val',)}),
            ("Choose output format", "Select Plot", {'fields':('operation_choice',)}),
        )
