from django import forms
from django.db import models
from django.forms.utils import flatatt
from django.utils.html import mark_safe, format_html
from django.urls import reverse
#for searching
from django.contrib.postgres.search import SearchVector

from django.apps import apps

from django_jinja_knockout.widgets import DisplayText
from django_jinja_knockout.forms import BootstrapModelForm, DisplayModelMetaclass
from db.models.object import Object

import graphviz as gv

class Result(Object):
    """
    Some kind of result from an analysis
    """
    base_name = "result"
    plural_name = "results"
    id_field = "uuid"
    has_upstream = True

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffeea8'}

    list_display = ('source', 'type', 'source_step', 'processes', 'samples', 'values', 'uuid')
    uuid = models.UUIDField(unique=True) #For QIIME2 results, this is the artifact UUID
    file = models.ForeignKey('File', on_delete=models.CASCADE, verbose_name="Result File Name", blank=True, null=True)
    source = models.CharField(max_length=255, verbose_name="Source Software/Instrument", blank=True, null=True)
    type = models.CharField(max_length=255, verbose_name="Result Type", blank=True, null=True)
    analysis = models.ForeignKey('Analysis', related_name='results', on_delete=models.CASCADE)
    # This process result is from this step
    source_step = models.ForeignKey('Step', on_delete=models.CASCADE, verbose_name="Source Step", blank=True, null=True)
    # Samples that this thing is the result for
    samples = models.ManyToManyField('Sample', related_name='results', verbose_name="Samples", blank=True)
    features = models.ManyToManyField('Feature', related_name='results', verbose_name="Features", blank=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)
    #from_provenance = models.BooleanField(default=False)

    values = models.ManyToManyField('Value', related_name="results", blank=True)

    def __str__(self):
        return self.get_detail_link()

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 self.type + " from " + self.source_step.name))

    @classmethod
    def get_display_form(cls):
        class DisplayForm(BootstrapModelForm,
                          metaclass=DisplayModelMetaclass):
            provenance = forms.CharField(max_length=4096, widget=DisplayText())
            graph = forms.CharField(max_length=4096, widget=DisplayText())
            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'all_upstream', \
                           'features', 'samples']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    initial=kwargs.setdefault('initial',{})
                    initial['graph'] = mark_safe(kwargs['instance'].get_stream_graph(values=True).pipe().decode().replace("\n",""))
                    initial['provenance'] = mark_safe(kwargs['instance'].simple_provenance_graph().pipe().decode().replace("\n",""))
                super().__init__(*args, **kwargs)
                self.fields.move_to_end('created_by')
                self.fields.move_to_end('categories')
        return DisplayForm

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector= (SearchVector('source', weight='A') +
                            SearchVector('type', weight='B') +
                            SearchVector('uuid', weight='C'))
        )

    def get_parameters(self):
        # Get the parameters for this Result, with respect to its source step
        parameters = {}
        for queryset in [self.source_step.values.filter(results=self),
                         self.analysis.process.values,
                         self.analysis.values,
                         self.values]:
            for value in queryset.filter(steps=self.source_step, type="parameter"):
                parameters[value.name] = value.content_object.value
        return parameters

    def related_samples(self, upstream=False):
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_features(self):
        return self.features.all()

    def related_steps(self, upstream=False):
        if not self.source_step:
            return apps.get_model("db", "Step").objects.none()
        steps = apps.get_model("db", "Step").objects.filter(pk=self.source_step.pk)
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_processes(self, upstream=False):
        processes = apps.get_model("db", "Process").objects.filter(pk=self.analysis.process.pk)
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_analyses(self):
        return apps.get_model("db", "Analysis").objects.filter(pk=self.analysis.pk)

    def simple_provenance_graph(self):
        dot = gv.Digraph("provenance", format='svg')
        dot.graph_attr.update(compound='true')
        dot.graph_attr.update(rankdir="LR")
        dot.graph_attr.update(size="10,10!")
        rn=self.get_node_attrs()
        rn['name']="R"
        an=self.analysis.get_node_attrs(values=False)
        an['name']="A"
        pn=self.analysis.process.get_node_attrs(values=False)
        pn['name']="P"
        sn=self.source_step.get_node_attrs(values=False)
        sn['name']="S"
        dot.node(**sn)
        dot.node(**rn)
        dot.node(**an)
        dot.node(**pn)
        dot.edges(["PA","AS","SR"])
        samplegraph = gv.Digraph("cluster0")
        sample_name = None
        nsamples = len(self.samples.all())
        for sample in self.samples.all()[0:3]:
            attrs = sample.get_node_attrs(values=False)
            attrs['name'] = "S%d" % (sample.pk,)
            sample_name = attrs['name']
            samplegraph.node(**attrs)
        if nsamples>3:
            nmore = nsamples - 3
            attrs = apps.get_model("db", "Sample").gv_node_style
            attrs['fontname'] = 'FreeSans'
            attrs['label'] = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr><tr><td colspan=\"3\"><b>%d more...</b></td></tr></table>>" % ("SAMPLE",nmore)
            attrs['name'] = "SX"
            samplegraph.node(**attrs)
        dot.subgraph(samplegraph)
        if sample_name is not None:
            dot.edge(sample_name, "R", ltail="cluster0")
        featuregraph = gv.Digraph("cluster1")
        feature_name = None
        nfeatures = len(self.features.all())
        for feature in self.features.all()[0:3]:
            attrs = feature.get_node_attrs(values=False)
            attrs['name'] = "S%d" % (feature.pk,)
            feature_name = attrs['name']
            featuregraph.node(**attrs)
        if nfeatures>3:
            nmore = nfeatures - 3
            attrs = apps.get_model("db", "Feature").gv_node_style
            attrs['fontname'] = 'FreeSans'
            attrs['label'] = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr><tr><td colspan=\"3\"><b>%d more...</b></td></tr></table>>" % ("FEATURE",nmore)
            attrs['name'] = "FX"
            featuregraph.node(**attrs)
        dot.subgraph(featuregraph)
        if feature_name is not None:
            dot.edge(feature_name, "R", ltail="cluster1")
        return dot
