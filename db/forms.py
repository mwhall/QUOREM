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
    Value, Parameter, Matrix,
    DataSignature,
    UploadFile, UserProfile, UploadMessage
)
from .models.object import Object

from django.forms import formset_factory, ModelForm

#Stuff for custom FieldSetForm
from django.forms.models import ModelFormOptions

from dal import autocomplete


class OrderedModelMultipleChoiceField(forms.ModelMultipleChoiceField):

    def clean(self, value):
        qs = super(OrderedModelMultipleChoiceField, self).clean(value)
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(value)])
        return qs.filter(pk__in=value).order_by(preserved)

#Base Forms and Display Forms

class UserProfileForm(ModelForm):
    #ModelForm will auto-generate fields which dont already exist
    #Therefore, creating fields prevents auto-generation.
    class Meta:
        model = UserProfile
        fields = ['user']

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

class NameLabelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s" % (obj.name,)

#### Investigation Forms

class InvestigationForm(ModelForm):
    class Meta:
        model = Investigation
        exclude = ['search_vector', 'values']

class InvestigationCreateForm(forms.ModelForm):
    class Meta:
        model = Investigation
        fields = ['name']
    def __init__(self, *args, **kwargs):
        super(InvestigationCreateForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'

class InvestigationDisplayForm(ModelForm):
    class Meta:
        model = Investigation
        exclude = ['search_vector', 'values']

class SampleForm(ModelForm):
#    investigations = NameLabelChoiceField(queryset = Investigation.objects.all())
    class Meta:
        model = Sample
        exclude = ['search_vector', 'values', 'investigations', 'features', 'upstream', 'all_upstream']

def get_step_link(form, value):
    if (value == None) or (value == ""):
        return ""
    if isinstance(value, int):
        name = Step.objects.get(pk=value).name
        return format_html('<a{}>{}</a>', flatatt({'href': reverse('step_detail', kwargs={'step_id': value})}), name)
    else:
        return Step.objects.get(name=value).get_detail_link()

class FeatureForm(ModelForm):
    class Meta:
        model = Feature
        exclude = ['search_vector', 'values', 'annotations']

class FeatureDisplayForm(ModelForm):
    measures = forms.CharField(max_length=4096, label="Measures")
    metadata = forms.CharField(max_length=4096, label="Metadata")
    class Meta:
        model = Feature
        exclude = ['search_vector', 'values']
    def __init__(self, *args, **kwargs):
        if kwargs.get('instance'):
            initial=kwargs.setdefault('initial',{})
            initial['measures'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.filter(type="measure") ]))
            initial['metadata'] = mark_safe("<br/>".join([str(x) for x in kwargs['instance'].values.filter(type="metadata") ]))
        super(FeatureDisplayForm, self).__init__(*args, **kwargs)

class ProcessForm(ModelForm):
    class Meta:
        model = Process
        exclude = ['search_vector', 'values', 'upstream', 'all_upstream']

class ProcessCreateForm(forms.ModelForm):
    class Meta:
        model = Process
        fields = ['name']
    def __init__(self, *args, **kwargs):
        super(ProcessCreateForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'


class ProcessDisplayForm(ModelForm):
    steps = forms.ModelMultipleChoiceField(queryset=Step.objects.all(), label="Steps")
    default_parameters = forms.CharField(max_length=4096)
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

class StepForm(ModelForm):
    class Meta:
        model = Step
        exclude = ('search_vector','values', 'upstream', 'all_upstream', 'processes')
    def get_upstream_link(self, value):
            return Result.objects.get(uuid=value).get_detail_link()
    def __init__(self, *args, **kwargs):
        super(StepForm, self).__init__(*args, **kwargs)
#        self.fields['values'].label = "Default Parameters"

class StepDisplayForm(ModelForm):
    downstream = forms.ModelMultipleChoiceField(queryset=Step.objects.none(), label="Downstream")
    default_parameters = forms.CharField(max_length=4096)
    node = forms.CharField(max_length=4096)
    graph = forms.CharField(max_length=4096)
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
#        widgets = {'upstream': DisplayText(get_text_method=get_step_link),
#                   'processes': DisplayText(get_text_method=get_process_link)}

# No ResultForm, we don't need to edit that one manually. Results come in with Upload Files

class ResultDisplayForm(ModelForm):
    parameters = forms.CharField(max_length=4096)
    def get_upstream_link(self, value):
       return Result.objects.get(uuid=value).get_detail_link()
    downstream = forms.ModelMultipleChoiceField(queryset=Result.objects.none(), label="Downstream")
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
#        widgets = {'upstream' : DisplayText(get_text_method=get_upstream_link),
#                   'all_upstream': DisplayText(get_text_method=get_upstream_link),
#                   'downstream': DisplayText(get_text_method=get_upstream_link),
#                   'features': DisplayText(get_text_method=get_feature_link),
#                   'source_step': DisplayText(get_text_method=get_step_link),
#                   'analysis': DisplayText(get_text_method=get_analysis_link)}

class AnalysisForm(ModelForm):
    class Meta:
        model = Analysis
        exclude = ('search_vector','values','extra_steps')

class AnalysisDisplayForm(ModelForm):
    default_parameters = forms.CharField(max_length=4096)
    def get_result_link(self, value):
        return Result.objects.get(uuid=value).get_detail_link()
    results = forms.ModelMultipleChoiceField(queryset=Result.objects.none(), label="Results")
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
#        widgets = {'process': DisplayText(get_text_method=get_process_link),
#                   'results': DisplayText(get_text_method=get_result_link)}


##### Plot Option Select Form

class TreeSelectForm(forms.Form):
    tree_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                         label="Phylogenetic Tree",
                                         widget=autocomplete.ModelSelect2(url='result-tree-autocomplete', attrs={"style": "flex-grow: 1", 'data-html': True}))

class TableCollapseForm(forms.Form):
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
    taxonomy_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                             label="Taxonomic Classification Set",
                                             widget=autocomplete.ModelSelect2(url='result-taxonomy-autocomplete',
                                                 forward=("count_matrix",),
                                                 attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
                                             
    normalize_methods = ["raw", "counts", "none", "proportion", "percent"]
    normalize_method = autocomplete.Select2ListChoiceField(choice_list=normalize_methods,
                                                           widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))

    tax_ranks = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species","Full"]
    taxonomic_level = autocomplete.Select2ListChoiceField(choice_list=tax_ranks,
                                                          widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))
    metadata_collapse = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Aggregation",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))

class PCoAPlotForm(forms.Form):
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
    measures = ['euclidean', 'l2', 'l1', 'manhattan', 'cityblock', 'braycurtis', 'canberra', 'chebyshev', 'correlation', 'cosine', 'dice', 'hamming', 'jaccard', 'kulsinski', 'mahalanobis', 'matching', 'minkowski', 'rogerstanimoto', 'russellrao', 'seuclidean', 'sokalmichener', 'sokalsneath', 'sqeuclidean', 'yule', 'wminkowski', 'nan_euclidean', 'haversine']
    measure = autocomplete.Select2ListChoiceField(required=True, choice_list=measures,
                                             widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                    'data-html': True}))
    metadata_colour = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Colour",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "data-placeholder": "Select metadata to colour Samples by",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))
    three_dimensional = forms.BooleanField(required=False, initial=False, label="3D Plot", widget=forms.CheckboxInput(attrs={"class":"big-checkbox"}))


class TablePlotForm(forms.Form):

    plot_types = ['bar', 'heatmap', 'area', 'box', 'violin']
    plot_type = autocomplete.Select2ListChoiceField(required=True, choice_list=plot_types,
                                             widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                    'data-html': True}))
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
    taxonomy_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                             label="Taxonomic Classification Set",
                                             widget=autocomplete.ModelSelect2(url='result-taxonomy-autocomplete',
                                                 forward=("count_matrix",),
                                                 attrs={"style": "flex-grow: 1; width: 50%", 'data-html': True, 'data-allow-clear': 'true'}))
                                             
    normalize_methods = ["raw", "counts", "none", "proportion", "percent"]
    normalize_method = autocomplete.Select2ListChoiceField(choice_list=normalize_methods,
                                                           widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))

    tax_ranks = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species","Full"]
    taxonomic_level = autocomplete.Select2ListChoiceField(choice_list=tax_ranks,
                                                          widget=autocomplete.ListSelect2(attrs={"style": "flex-grow: 1", 
                                                                                                 'data-html': True}))
    plot_height = forms.IntegerField(initial=750)
    metadata_collapse = forms.ModelChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Aggregation",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "data-placeholder": "Select metadata to collapse Samples on",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))
    metadata_sort = OrderedModelMultipleChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Sort",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2Multiple(url='sample-metadata-autocomplete',
                                                                                               forward=("count_matrix",),
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                   "style": "flex-grow: 1; width: 50%",
                                                                                                      "data-html": True}))

    plot_height = forms.IntegerField(initial=750, label="Height (px)")
    n_taxa = forms.IntegerField(initial=25, label="Plot N Most Abundant Taxa")
    label_bars = forms.BooleanField(required=False, initial=True, label="Taxonomic Labels on Bars", widget=forms.CheckboxInput(attrs={"class":"big-checkbox"}))

class TaxBarSelectForm(forms.Form):
    taxonomy_result = forms.ModelChoiceField(queryset=Result.objects.all(),
                                             label="Taxonomic Classification Set",
                                             widget=autocomplete.ModelSelect2(url='result-taxonomy-autocomplete',
                                                                              attrs={"style": "flex-grow: 1;", 'data-html': True}))
    count_matrix = forms.ModelChoiceField(queryset=Result.objects.all(),
                                          label="Count Matrix",
                                          widget=autocomplete.ModelSelect2(url='result-countmatrix-autocomplete',
                                          forward=("taxonomy_result",),
                                          attrs={"style": "flex-grow: 1", 'data-html': True}))
    samples_from_investigation = forms.ModelChoiceField(queryset=Investigation.objects.all(),
                                                        required=False,
                                                        label="Select Samples from Investigation",
                                                        widget=autocomplete.ModelSelect2(url='object-investigation-autocomplete',
                                                                                                 attrs={"data-allow-clear":"true",
                                                                                                        "style": "flex-grow: 1",
                                                                                                        "data-html": True}))
    samples = forms.ModelMultipleChoiceField(queryset=Sample.objects.all(),
                                          required=False,
                                          label="Samples",
                                          widget=autocomplete.ModelSelect2Multiple(url='object-sample-autocomplete',
                                                                                   forward=('count_matrix',),
                                                                                   attrs={"data-allow-clear": "true", "style": "flex-grow: 1", 'data-html': True}))
    taxonomic_level = autocomplete.Select2ListChoiceField(widget=autocomplete.ListSelect2(url='taxonomic-level-autocomplete', attrs={"style": "flex-grow: 1", 
        'data-html': True}))
    plot_height = forms.IntegerField(initial=750)
#    def __init__(self, *args, **kwargs):
#        super().__init__(*args, **kwargs)
#        self.fields['plot_height'].widget.attrs.update({'placeholder': 750,'default':750})
    metadata_sort_by = OrderedModelMultipleChoiceField(queryset=DataSignature.objects.all(),
                                                      label="Metadata for Sort",
                                                      required=False,
                                                      widget=autocomplete.ModelSelect2Multiple(url='data-signature-autocomplete',
                                                                                               attrs={"data-allow-clear": "true",
                                                                                                      "style": "flex-grow: 1",
                                                                                                      "data-html": True}))
    plot_height = forms.IntegerField(initial=750, label="Height (px)")
    n_taxa = forms.IntegerField(initial=25, label="Plot N Most Abundant Taxa")
    label_bars = forms.BooleanField(initial=True, label="Taxonomic Labels on Bars", widget=forms.CheckboxInput(attrs={"class":"big-checkbox"}))

class AnalysisSelectForm(forms.Form):
    analysis = forms.ModelChoiceField(queryset=Analysis.objects.all(),
                                      label="Analysis",
                                      widget=autocomplete.ModelSelect2(url='object-analysis-autocomplete',
                                                                       attrs={"data-allow-clear": "true", "style": "flex-grow: 1", "data-html": True}))

class AnalysisCreateForm(forms.ModelForm):
    class Meta:
        model = Analysis
        fields = ['name','process']
        widgets = {'process': autocomplete.ModelSelect2(url='object-process-autocomplete',
                                                        attrs={"data-allow-clear": "true", "style": "flex-grow: 1", "data-html": True})}
    def __init__(self, *args, **kwargs):
        super(AnalysisCreateForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            #Simple way to bootstrapify the input
            visible.field.widget.attrs['class'] = 'form-control'

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
            ('Select Dependent and Independent Variables', 'Select Variables', {'fields': ('field1', 'field2')}),
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
        ('2', 'Features'),
        ('3', 'Results'),

    )
    #In each field, define class labels for widgets where field change affects subesqeuent fields.
    #These class labels will have JS event listeneres attached where relevant.
    #invField = forms.ModelMultipleChoiceField(queryset = Investigation.objects.all(),
    #                                  label="Select Investigation(s)")
    x_val_category = forms.ChoiceField(choices = MODEL_CHOICES, label="Select X-value category.", widget=forms.Select(attrs={'class':'x-val'}))
    x_val = forms.CharField(widget=forms.Select, label="Select X Value.")

#    y_val_category = forms.ChoiceField(choices = MODEL_CHOICES, label="Select Y-value category.")
    y_val = forms.CharField(widget=forms.Select, label="Select Y Value.")

    operation_choice = forms.ChoiceField(choices = (('1','Scatter'),('2','Contiuous')),
                                        label="Select Plot Type.")

    class Meta:
        fieldsets = (
            ('Choose Dependent Variable', "Select X", {'fields': ('x_val_category', 'x_val',)}),
            ("Choose Independent Variable", "Select Y", {'fields': ('y_val',)}),
            ("Choose output format", "Select Plot", {'fields':('operation_choice',)}),
        )

class ValueTableForm(forms.Form):
    #need a field for choosing a dependent variable
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

    depField = forms.ChoiceField(choices=CHOICES, label="Object")
    depValue = forms.CharField(widget=forms.SelectMultiple(attrs={'tabindex':"0"}), label="Select Value")

    #independent variables
#    indField_0 = forms.CharField(widget=forms.Select, label="Select Related Model(s)")
#    indValue_0 = forms.CharField(widget=forms.SelectMultiple(attrs={'tabindex':"0"}), label="Select Value(s)")

    #??? how do filters get made???
    class Meta:
        fieldsets = (
            ("Select the object type and values",
             "Select Object", {'fields': ('depField', 'depValue')}),
        #    ("Select the independent variable (rows of the table; data tuples)",
        #     "Select Independent", {'fields': ('indField_0', 'indValue_0')}),
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
