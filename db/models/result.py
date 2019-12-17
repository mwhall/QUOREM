from collections import OrderedDict

from django import forms
from django.db import models
from django.forms.utils import flatatt
from django.utils.html import mark_safe, format_html
from django.urls import reverse
#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.contenttypes.models import ContentType

from django.apps import apps

from db.models.object import Object
from db.models.step import Step

import graphviz as gv
from combomethod import combomethod

class Result(Object):
    base_name = "result"
    plural_name = "results"
    has_upstream = True

    description = "A Result is something that is produced by a Step and is required for registering Measures\nResults link Measures to the Analysis and Process chain that generated them"

    grid_fields = ["name", "source_step", "analysis"]
    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffeea8'}

    name = models.CharField(max_length=255, unique=True) #For QIIME2 results, this can still be the UUID
    analysis = models.ForeignKey('Analysis', related_name='results', on_delete=models.CASCADE)
    # This process result is from this step
    source_step = models.ForeignKey('Step', on_delete=models.CASCADE, verbose_name="Source Step")
    # Samples that this thing is the result for
    samples = models.ManyToManyField('Sample', related_name='results', verbose_name="Samples", blank=True)
    features = models.ManyToManyField('Feature', related_name='results', verbose_name="Features", blank=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="results", blank=True)

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 self.name + " from " + self.source_step.name))

    def get_parameters(self, step_field="pk"):
        Parameter = apps.get_model("db.Parameter")
        step = self.source_step
        res_params = dict([(x.signature.get().name, 
                           (x, 'result')) 
                            for x in self.values.instance_of(Parameter).filter(steps=step)])
        anal_params = self.analysis.get_parameters(steps=step.qs())[step.pk]
        anal_params.update(res_params)
        if not anal_params:
            anal_params = {}
        return {getattr(step, step_field): anal_params}

    @classmethod
    def infer_step_upstream(self, results=None):
        if results is None:
            results = Result.objects.all()
        results = results.filter(upstream__isnull=False)
        for res in results:
            upsteps = Step.objects.filter(pk__in=res.upstream.values("source_step"))
            res.source_step.update(upstream=upsteps)

    @classmethod
    def get_filters(cls):
        return OrderedDict([('source_step', {'type': 'choices',
                                             'choices': cls.objects.values_list("source_step__pk", "source_step__name").distinct(),
                                             'active_choices': []}),
                            ('analysis', {'type': 'choices',
                                             'choices': cls.objects.values_list("analysis__pk", "analysis__name").distinct(),
                                             'active_choices': []}),
#                            ('qiime2_version', {'type': 'choices',
#                                             'choices': apps.get_model("db.VersionDatum").objects.filter(values__name="qiime2", values__results__isnull=False).values_list("pk", "value").distinct(),
#                                             'active_choices': []}),
                                           ])

    def html_features(self):
        feature_count = self.features.count()
        accordions = {'features': {'heading': format_html('Show Features ({})', str(feature_count))}}
        content = ""
        for feature in self.features.all():
            content += format_html("{}<BR/>", mark_safe(str(feature)))
        accordions['features']['content'] = content
        return self._make_accordion("features", accordions)

    def html_samples(self):
        sample_count = self.samples.count()
        accordions = {'samples': {'heading': format_html('Show Samples ({})', str(sample_count))}}
        content = ""
        for sample in self.samples.all():
            content += format_html("{}<BR/>", mark_safe(str(sample)))
        accordions['samples']['content'] = content
        return self._make_accordion("samples", accordions)

    @classmethod
    def get_display_form(cls):
        from django_jinja_knockout.widgets import DisplayText
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            provenance = forms.CharField(max_length=4096, widget=DisplayText())
            sample_accordion = forms.CharField(widget=DisplayText(), label="Samples")
            feature_accordion = forms.CharField(widget=DisplayText(), label="Features")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'all_upstream', 'features', 'samples']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['provenance'] = mark_safe(kwargs['instance'].simple_provenance_graph().pipe().decode().replace("\n",""))
                    kwargs['initial']['sample_accordion'] = mark_safe(kwargs['instance'].html_samples())
                    kwargs['initial']['feature_accordion'] = mark_safe(kwargs['instance'].html_features())
                super().__init__(*args, **kwargs)
        return DisplayForm

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector= (SearchVector('source', weight='A') +
                            SearchVector('type', weight='B') +
                            SearchVector('uuid', weight='C'))
        )

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

    def get_qiime2_command(self):
        #First, check that the Result is a QIIME artifact
        plugin = ""
        cmd = ""
        input_results = ""
        input_parameters = ""

    def simple_provenance_graph(self):
        dot = gv.Digraph("provenance", format='svg')
        dot.graph_attr.update(compound='true')
        dot.graph_attr.update(rankdir="LR")
        dot.graph_attr.update(size="10,10!")
        rn=self.get_node_attrs(highlight=True)
        rn['name']="R"
        an=self.analysis.get_node_attrs()
        an['name']="A"
        pn=self.analysis.process.get_node_attrs()
        pn['name']="P"
        sn=self.source_step.get_node_attrs()
        sn['name']="S"
        dot.node(**sn)
        dot.node(**rn)
        dot.node(**an)
        dot.node(**pn)
        dot.edges(["PA","AS","SR"])
        samplegraph = gv.Digraph("cluster0")
        sample_name = None
        nsamples = self.samples.count()
        for sample in self.samples.all()[0:3]:
            attrs = sample.get_node_attrs(show_values=False)
            attrs['name'] = "S%d" % (sample.pk,)
            sample_name = attrs['name']
            samplegraph.node(**attrs)
        if nsamples>3:
            nmore = nsamples - 3
            attrs = sample.get_node_attrs(highlight=False, show_values=False)
            attrs['fontname'] = 'FreeSans'
            attrs['label'] = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr><tr><td colspan=\"3\"><b>%d more...</b></td></tr></table>>" % ("SAMPLE",nmore)
            attrs['name'] = "SX"
            samplegraph.node(**attrs)
        featuregraph = gv.Digraph("cluster1")
        feature_name = None
        nfeatures = self.features.count()
        for feature in self.features.all()[0:3]:
            attrs = feature.get_node_attrs(show_values=False)
            attrs['name'] = "F%d" % (feature.pk,)
            feature_name = attrs['name']
            featuregraph.node(**attrs)
        if nfeatures>3:
            nmore = nfeatures - 3
            attrs = feature.get_node_attrs(highlight=False, show_values=False)
            attrs['fontname'] = 'FreeSans'
            attrs['label'] = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr><tr><td colspan=\"3\"><b>%d more...</b></td></tr></table>>" % ("FEATURE",nmore)
            attrs['name'] = "FX"
            featuregraph.node(**attrs)
        dot.subgraph(featuregraph)
        dot.subgraph(samplegraph)
        if sample_name is not None:
            dot.edge(sample_name, "R", ltail="cluster0")
        if feature_name is not None:
            dot.edge(feature_name, "R", ltail="cluster1")
        return dot
