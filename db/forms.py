from django import forms
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.db import models
from .models import (
    Investigation,
    Process, Step, Analysis,
    Result,
    Sample, Feature,
    Value,
    File, UserProfile, UploadMessage
)

from django_jinja_knockout.forms import (
    DisplayModelMetaclass, FormWithInlineFormsets, BootstrapModelForm,
    ko_inlineformset_factory, ko_generic_inlineformset_factory, WidgetInstancesMixin,
    BootstrapModelForm
)
from django_jinja_knockout.widgets import ForeignKeyGridWidget, DisplayText

from django.forms import inlineformset_factory, ModelForm

#Stuff for custom FieldSetForm
from django.forms.models import ModelFormOptions

from dal import autocomplete

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

class UserProfileForm(BootstrapModelForm):
    #ModelForm will auto-generate fields which dont already exist
    #Therefore, creating fields prevents auto-generation.
    class Meta:
        model = UserProfile
        fields = ['user']



class UploadForm(WidgetInstancesMixin, BootstrapModelForm):
    class Meta:
        model = File
        fields = ['upload_file']

UserUploadFormset = ko_inlineformset_factory(UserProfile,
                                             File,
                                             form=UploadForm,
                                             extra=0,
                                             min_num=1)

################ Upload Forms
class ArtifactUploadForm(ModelForm):
    analysis = forms.ModelChoiceField(queryset=Analysis.objects.all(), empty_label="Select an Analysis")
    register_provenance = forms.BooleanField(initial=False, required=False, label="Register Provenance")
    class Meta:
        model = File
        #exclude = ('userprofile', )
        fields = ('analysis', 'register_provenance', 'upload_file',)
    def __init__(self, *args, **kwargs):
        self.userprofile = kwargs.pop('userprofile')
        super(ArtifactUploadForm, self).__init__(*args, **kwargs)

class SpreadsheetUploadForm(ModelForm):
    class Meta:
        model = File
        #exclude = ('userprofile', )
        fields = ('upload_file',)
    def __init__(self, *args, **kwargs):
        self.userprofile = kwargs.pop('userprofile')
        super(SpreadsheetUploadForm, self).__init__(*args, **kwargs)

##########################


#This form used only for display purposes
class FileDisplayForm(WidgetInstancesMixin,
                                BootstrapModelForm,
                                metaclass=DisplayModelMetaclass):
        class Meta:
            model=File
            fields = '__all__'

class ErrorDisplayForm(WidgetInstancesMixin, BootstrapModelForm,
                        metaclass=DisplayModelMetaclass):
    class Meta:
        model = UploadMessage
        fields = '__all__'



FileDisplayErrorFormset = ko_inlineformset_factory(
                                                File,
                                                UploadMessage,
                                                form=ErrorDisplayForm,
                                                extra=0,
                                                min_num=0,
                                                can_delete=False)

class FileDisplayWithInlineErrors(FormWithInlineFormsets):
    FormClass = FileDisplayForm
    FormsetClasses =[FileDisplayErrorFormset]
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

class InvestigationForm(BootstrapModelForm):
    class Meta:
        model = Investigation
        exclude = ['search_vector']
        attrs = {'data-minimum-input-length':3,
                 'data-placeholder': 'Type to search...'}
        widgets = {'values': autocomplete.ModelSelect2Multiple(url='value-autocomplete',
                                                               attrs=attrs)}

class InvestigationDisplayForm(BootstrapModelForm,
                               metaclass=DisplayModelMetaclass):
    class Meta:
        model = Investigation
        exclude = ['search_vector']

class SampleForm(BootstrapModelForm):
#    investigations = NameLabelChoiceField(queryset = Investigation.objects.all())
    class Meta:
        model = Sample
        exclude = ['search_vector']

def get_step_link(form, value):
    if (value is None) or (value is ""):
        return ""
    if isinstance(value, int):
        name = Step.objects.get(pk=value).name
        return format_html('<a{}>{}</a>', flatatt({'href': reverse('step_detail', kwargs={'step_id': value})}), name)
    else:
        return Step.objects.get(name=value).get_detail_link()


class SampleDisplayForm(WidgetInstancesMixin, BootstrapModelForm, metaclass=DisplayModelMetaclass):
    measures = forms.CharField(max_length=4096, label="Measures", widget=DisplayText())
    metadata = forms.CharField(max_length=4096, label="Metadata", widget=DisplayText())
    class Meta:
        #def get_name(self, value):
        #    return format_html('<a{}>{}</a>', flatatt({'href': reverse('sample_detail', kwargs={'sample_id': self.instance.pk})}), self.instance.name)
        def get_investigations(self, value):
            return ",".join([x.get_detail_link() for x in self.instance.investigations.all()])
        def get_analysis_link(self, value):
            if (value is None) or (value is ""):
                return ""
            return Analysis.objects.get(name=value).get_detail_link()

        model = Sample
        exclude = ['search_vector', 'values']
        #widgets = {'name': DisplayText(get_text_method=get_name),
        widgets={'investigations': DisplayText(get_text_method=get_investigations),
                'source_step': DisplayText(get_text_method=get_step_link),
                'analysis': DisplayText(get_text_method=get_analysis_link)}
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['measures'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.filter(type="measure") ]))
            initial['metadata'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.filter(type="metadata") ]))
        super(SampleDisplayForm, self).__init__(*args, **kwargs)


class FeatureForm(BootstrapModelForm):
    class Meta:
        model = Feature
        exclude = ['search_vector']

class FeatureDisplayForm(WidgetInstancesMixin, BootstrapModelForm, metaclass=DisplayModelMetaclass):
    measures = forms.CharField(max_length=4096, label="Measures", widget=DisplayText())
    metadata = forms.CharField(max_length=4096, label="Metadata", widget=DisplayText())
    class Meta:
        model = Feature
        exclude = ['search_vector', 'values']
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['measures'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.filter(type="measure") ]))
            initial['metadata'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.filter(type="metadata") ]))
        super(FeatureDisplayForm, self).__init__(*args, **kwargs)

class ProcessForm(BootstrapModelForm):
    class Meta:
        model = Process
        exclude = ['search_vector']

class ProcessDisplayForm(BootstrapModelForm, metaclass=DisplayModelMetaclass):
    steps = forms.ModelMultipleChoiceField(queryset=Step.objects.all(), label="Steps", widget=DisplayText(get_text_method=get_step_link))
    default_parameters = forms.CharField(max_length=4096, widget=DisplayText())
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['steps'] = [x for x in kwargs['instance'].steps.all()]
            # This complication makes sure we only have the default parameters
            initial['default_parameters'] = mark_safe("<br/>".join([str(x.steps.get().name) + ", " + str(x) for x in kwargs['instance'].values.annotate(stepcount=models.Count("steps"), processcount=models.Count("processes")).filter(stepcount=1, processcount=1).filter(samples__isnull=True, analyses__isnull=True, results__isnull=True, type='parameter') ]))
        super(ProcessDisplayForm, self).__init__(*args, **kwargs)
        self.fields.move_to_end('steps')
        self.fields.move_to_end('categories')

    class Meta:
        model = Process
        exclude = ['search_vector', 'values']

class StepForm(BootstrapModelForm):
    class Meta:
        model = Step
        exclude = ('search_vector',)
    def get_upstream_link(self, value):
            return Result.objects.get(uuid=value).get_detail_link()
    def __init__(self, *args, **kwargs):
        super(StepForm, self).__init__(*args, **kwargs)
        self.fields['values'].label = "Default Parameters"

class StepDisplayForm(WidgetInstancesMixin, BootstrapModelForm, metaclass=DisplayModelMetaclass):
    downstream = forms.ModelMultipleChoiceField(queryset=Step.objects.none(), label="Downstream", widget=DisplayText(get_text_method=get_step_link))
    default_parameters = forms.CharField(max_length=4096, widget=DisplayText())
    node = forms.CharField(max_length=4096, widget=DisplayText())
    graph = forms.CharField(max_length=4096, widget=DisplayText())
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['downstream'] = [x.name for x in kwargs['instance'].downstream.all()]
            # This complication makes sure we only have the default parameters
            initial['default_parameters'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.annotate(stepcount=models.Count("steps")).filter(stepcount=1).filter(processes__isnull=True, samples__isnull=True, analyses__isnull=True, results__isnull=True) ]))
            initial['node'] = mark_safe(kwargs['instance'].get_node(values=True).pipe().decode().replace("\n",""))
            initial['graph'] = mark_safe(kwargs['instance'].get_stream_graph().pipe().decode().replace("\n",""))
        super(StepDisplayForm, self).__init__(*args, **kwargs)
        self.fields.move_to_end('upstream')
        self.fields.move_to_end('categories')

    class Meta:
        model = Step
        exclude = ('search_vector', 'values')
        def get_process_link(self, value):
            return Process.objects.get(name=value).get_detail_link()
        widgets = {'upstream': DisplayText(get_text_method=get_step_link),
                   'processes': DisplayText(get_text_method=get_process_link)}

# No ResultForm, we don't need to edit that one manually. Results come in with Upload Files

class ResultDisplayForm(WidgetInstancesMixin, BootstrapModelForm, metaclass=DisplayModelMetaclass):
    parameters = forms.CharField(max_length=4096, widget=DisplayText())
    def get_upstream_link(self, value):
       return Result.objects.get(uuid=value).get_detail_link()
    downstream = forms.ModelMultipleChoiceField(queryset=Result.objects.none(), label="Downstream", widget=DisplayText(get_text_method=get_upstream_link))
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['downstream'] = [x.uuid for x in kwargs['instance'].downstream.all()]
            initial['parameters'] = mark_safe("</br>".join([x.name + ": " + str(x.content_object.value) for x in kwargs['instance'].values.annotate(stepcount=models.Count("steps"), resultcount=models.Count("results")).filter(stepcount=1, resultcount=1, type="parameter", analyses__isnull=True, samples__isnull=True, processes__isnull=True) ]))
        super(ResultDisplayForm, self).__init__(*args, **kwargs)
        self.fields.move_to_end('upstream')
        #self.fields.move_to_end('downstream')
        self.fields.move_to_end('categories')
    class Meta:
        model = Result
        exclude = ['search_vector', 'samples', 'features', 'values']
        def get_feature_link(self, value):
            return Feature.objects.get(name=value).get_detail_link()
        def get_upstream_link(self, value):
            return Result.objects.get(uuid=value).get_detail_link()
        def get_analysis_link(self, value):
            return Analysis.objects.get(name=value).get_detail_link()
        widgets = {'upstream' : DisplayText(get_text_method=get_upstream_link),
                   'all_upstream': DisplayText(get_text_method=get_upstream_link),
                   'downstream': DisplayText(get_text_method=get_upstream_link),
                   'features': DisplayText(get_text_method=get_feature_link),
                   'source_step': DisplayText(get_text_method=get_step_link),
                   'analysis': DisplayText(get_text_method=get_analysis_link)}

class AnalysisForm(BootstrapModelForm):
    class Meta:
        model = Analysis
        exclude = ('search_vector','values',)

class AnalysisDisplayForm(WidgetInstancesMixin, BootstrapModelForm, metaclass=DisplayModelMetaclass):
    default_parameters = forms.CharField(max_length=4096, widget=DisplayText())
    def get_result_link(self, value):
        return Result.objects.get(uuid=value).get_detail_link()
    results = forms.ModelMultipleChoiceField(queryset=Result.objects.none(), label="Results", widget=DisplayText(get_text_method=get_result_link))
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['results'] = [x.uuid for x in kwargs['instance'].results.all()]
            initial['default_parameters'] = mark_safe("<br/>".join([str(x.steps.get().name) + ", " + str(x) for x in kwargs['instance'].values.annotate(stepcount=models.Count("steps"), analysiscount=models.Count("analyses")).filter(stepcount=1, analysiscount=1).filter(samples__isnull=True, processes__isnull=True, results__isnull=True, type='parameter') ]))
        super(AnalysisDisplayForm, self).__init__(*args, **kwargs)
        self.fields.move_to_end('categories')
    class Meta:
        model = Analysis
        exclude = ('search_vector', 'values')
        def get_result_link(self, value):
            return Result.objects.get(uuid=value).get_detail_link()
        def get_process_link(self, value):
            return Process.objects.get(name=value).get_detail_link()
        widgets = {'process': DisplayText(get_text_method=get_process_link),
                   'results': DisplayText(get_text_method=get_result_link)}


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

class ValueTableForm(forms.Form):
    #need a field for choosing a dependant variable
    CHOICES = [
                ('', "Select..."),
                ('1', 'Investigation'),
                ('2', 'Sample'),
                ('3', 'Feature'),
                ('4', 'Step'),
                ('5', 'Process'),
                ('6', 'Analysis'),
                ('7', 'Result'),
              ]

    depField = forms.ChoiceField(choices=CHOICES)
    depValue = forms.CharField(widget=forms.SelectMultiple(attrs={'tabindex':"0"}), label="Select Value")

    #independant variables
    indField_0 = forms.CharField(widget=forms.Select, label="Select Related Model(s)")
    indValue_0 = forms.CharField(widget=forms.SelectMultiple(attrs={'tabindex':"0"}), label="Select Value(s)")

    #??? how do filters get made???
    class Meta:
        fieldsets = (
            ("Select the dependant variable (rows of the table; data tuples)",
             "Select Dependant", {'fields': ('depField', 'depValue')}),
            ("Select the independant variable (rows of the table; data tuples)",
             "Select Independant", {'fields': ('indField_0', 'indValue_0')}),
        )

    """
    Not sure if i need this at all? Maybe can get JS to call a view instead
    """
    """
    def clean(self):
        print('clean')
        print(self)
        indVals = set()
        i = 0
        field_name = 'indField_%s' % (i,)
        val_name = 'indValue_%s' % (i,)
        print(self.cleaned_data)
        while self.cleaned_data.get(field_name):
            field = self.cleaned_data[field_name]
            print(field)
            values = self.cleaned_data[val_name]
            print("***\n", values)
            i += 1
            field_name = 'indField_%s' % (i,)
            val_name = 'indValue_%s' % (i,)
    """
