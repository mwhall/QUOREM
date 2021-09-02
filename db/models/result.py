from collections import OrderedDict
from textwrap import fill, wrap
import colour

from django import forms
from django.db import models
from django.forms.utils import flatatt
from django.utils.html import mark_safe, format_html
from django.urls import reverse
#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.contenttypes.models import ContentType
from django.views.generic.detail import DetailView

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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.infer_step_upstream(results=self.qs())

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 self.name))

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

    def get_artifact_url(self):
        if self.has_value("uploaded_artifact", "file"):
            return self.get_value("uploaded_artifact", "file").upload_file.url
        else:
            return None

    def get_artifact_badge(self):
        if self.has_value('uploaded_artifact'):
            href = 'href="/data-artifact?result_id=%d"' % (self.pk,)
            badge_type = 'success'
        else:
            href='href="#"'
            badge_type = 'secondary'
        html_val = '<a class="badge badge-%s badge-pill" %s><i class="fas fa-file-download"></i></a></li>' % (badge_type, href)
        return mark_safe(html_val)

    def get_artifact_uploader(self):
        if self.has_value('uploaded_artifact', "file"):
            username = Result.objects.get(pk=self.pk).get_value("uploaded_artifact","file").userprofile.user.username
            return username
        else:
            return ""

    def get_result_type(self):
        if self.has_value("qiime2_type", "value"):
            return self.get_value("qiime2_type", "value")
        else:
            return "Unknown Result Type"

    def human_short(self):
        q2_type = self.get_result_type()
        #Do your best to find the most sensible string to describe the Result at hand
        if q2_type == "FeatureData[Sequence]":
            if self.source_step.name in ["dada2__denoise_paired", "dada2__denoise_single"]:
                return "Representative Sequences from DADA2"
            elif self.source_step.name in ["rescript__dereplicate","rescript__filter_seqs_length_by_taxon","rescript__cull_seqs"]:
                return "Reference Sequence File from qiime2 Plugin Rescript"
            elif self.source_step.name == "qiime2_import":
                return "Feature Sequences imported to qiime2"
            else:
                return q2_type
        elif q2_type == "FeatureData[AlignedSequence]":
            if self.source_step.name == "alignment__mask":
                return "Masked Aligned Sequences"
            elif self.source_step.name == "alignment__mafft":
                return "Sequences Aligned by MAFFT"
            else:
                return "Aligned Sequences"
        elif q2_type == "FeatureData[RNASequence]":
            if self.source_step.name == "rescript__get_silva_data":
                return "SILVA Reference RNA"
            else:
                return q2_type
        elif q2_type == "FeatureTable[Frequency]":
            if self.source_step.name == "taxa__collapse":
                return "Table Collapsed by Taxonomy"
            elif self.source_step.name in ["dada2__denoise_paired", "dada2__denoise_single"]:
                return "ASV Table from DADA2"
            elif self.source_step.name == "feature-table__filter_samples":
                source_table = self.upstream.first().human_short()
                return "Filtered %s" % (source_table,)
            elif self.source_step.name == "diversity__core_metrics":
                return "Intermediate Table from Diversity Pipeline"
            elif self.source_step.name == "feature-table__rarefy":
                return "Rarefied Table"
            else:
                return q2_type
        elif q2_type == "FeatureData[Taxonomy]":
            if self.source_step.name == "feature-classifier__classify_sklearn":
                return "Predicted Taxonomic Classifications"
            elif self.source_step.name == "rescript__dereplicate":
                return "Reference Taxonomy File from qiime2 Plugin Rescript"
            elif self.source_step.name == "rescript__get_silva_data":
                return "SILVA Reference Taxonomy"
            elif self.source_step.name == "qiime2_import":
                return "Taxonomy File imported to qiime2"
            else:
                return q2_type
        elif q2_type == "SampleData[PairedEndSequencesWithQuality]":
            if self.source_step.name == "qiime2_import":
                return "Paired-End Sequences Imported to qiime2"
            else:
                return q2_type
        elif q2_type == "Phylogeny[Rooted]":
            if self.source_step.name == "qiime2_import":
                return "Phylogenetic Tree Imported to qiime2"
            elif self.source_step.name == "phylogeny__midpoint_root":
                return "Rooted Phylogenetic Tree"
            else:
                return "Rooted Phylogenetic Tree"
        elif q2_type == "Phylogeny[Unrooted]":
            if self.source_step.name == "phylogeny__fasttree":
                return "Unrooted Phylogenetic Tree from FastTree"
            else:
                return "Unrooted Phylogenetic Tree"
        elif q2_type == "FeatureData[SILVATaxidMap]":
            return "SILVA Reference Map"
        elif q2_type == "FeatureData[SILVATaxonomy]":
            return "SILVA Reference Taxonomy"
        elif q2_type == "FeatureData[Taxonomy]":
            if self.source_step.name == "qiime2_import":
                return "Taxonomic Reference Imported to qiime2"
            else:
                return q2_type
        elif q2_type == "TaxonomicClassifier":
            if self.source_step.name == "rescript__evaluate_fit_classifier":
                return "Taxonomic Classifier from qiime2 Plugin Rescript"
            elif self.source_step.name == "feature-classifier__fit_classifier_naive_bayes":
                return "Taxonomic Classifier from qiime2 Feature Classifier"
            else:
                return q2_type
        elif q2_type == "SampleData[DADA2Stats]":
            return "DADA2 Denoise Statistics File"
        elif q2_type == "SampleData[AlphaDiversity]":
            return "Alpha Diversity Values"
        elif q2_type == "SampleData[AlphaDiversity] % Properties(['phylogenetic'])":
            return "Alpha Diversity Values, Phylogenetic"
        elif q2_type == "Visualization":
            if self.source_step.name == "feature-table__summarize":
                return "Table Summary Visualization"
            elif self.source_step.name == "demux__summarize":
                return "Quality Summary Visualization"
            elif self.source_step.name == "taxa__barplot":
                return "Taxonomic Barplot Visualization"
            else:
                return "%s from %s" % (q2_type, self.source_step.name)
        else:
            return q2_type

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
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            parameters = forms.CharField(label="Parameters (non-default if bold)")
            provenance = forms.CharField(max_length=4096)
            sample_accordion = forms.CharField(label="Samples")
            feature_accordion = forms.CharField(label="Features")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'all_upstream', 'features', 'samples']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['provenance'] = mark_safe(kwargs['instance'].simple_provenance_graph().pipe().decode().replace("<svg ", "<svg class=\"img-fluid\" ").replace("\n","").replace('pt"','"'))
                    kwargs['initial']['sample_accordion'] = mark_safe(kwargs['instance'].html_samples())
                    kwargs['initial']['feature_accordion'] = mark_safe(kwargs['instance'].html_features())
                    kwargs['initial']['parameters'] = mark_safe("<BR>".join([format_html("<b>{}: {} (set by {})</b>" if dat[1]=="result" else "{}: {} (set by {})", name, str(dat[0].data.get().get_value()), dat[1].capitalize()) for name, dat in kwargs['instance'].get_parameters()[kwargs['instance'].source_step.pk].items()]))
                super().__init__(*args, **kwargs)
                self.fields.move_to_end("value_accordion")
                self.fields.move_to_end("graph")
                self.fields["upstream"].label = "Input Results"
                self.fields["source_step"].label = "Output By Step"
        return DisplayForm

    @classmethod
    def get_detail_view(cls, as_view=False):
        class ResultDetailView(DetailView):
            pk_url_kwarg = 'result_id'
            form = cls.get_display_form()
            queryset = cls.objects.all()
            template_name = "result_detail.htm"
            def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                #Add to context dict to make available in template
                obj = self.get_object()
                context['samples_html'] = mark_safe(obj.html_samples())
#                context['features_html'] = mark_safe(obj.html_features())
                context['provenance_graph'] = mark_safe(obj.simple_provenance_graph().pipe().decode().replace("<svg ", "<svg id=\"provenancegraph\" class=\"img-fluid\" ").replace("\n",""))
                context['stream_graph'] = mark_safe(obj.get_stream_graph().pipe().decode().replace("<svg ", "<svg id=\"streamgraph\" class=\"img-fluid\" ").replace("\n", ""))
#                context['values_html'] = mark_safe(obj.html_values())
                context['has_uploaded_artifact'] = obj.get_artifact_url()
                context['q2type'] = obj.get_result_type()
                return context
        if as_view:
            return ResultDetailView.as_view()
        else:
            return ResultDetailView

    @classmethod
    def get_crud_form(cls):
        CrudForm = super().get_crud_form()
        class ResultCrudForm(CrudForm):
            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'samples',
                           'features', 'upstream', 'all_upstream']
        return ResultCrudForm

    @classmethod
    def update_search_vector(cls):
        sv = (SearchVector('name', weight='A') +
                SearchVector('source_step__name', weight='B') +
                SearchVector('values__signature__name', weight='C') +
                SearchVector('values__signature__data', weight='D')

        )
        cls.objects.update(
            search_vector= sv
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

    def get_node_attrs(self, show_values=True, highlight=False, value_counts=None):
        htm = "<<table border=\"0\">"
#        htm = "<<table border=\"0\"><tr><td colspan=\"2\"><b>%s</b></td></tr>" % (self.base_name.upper(),)
        if not show_values:
           sep = ""
        else:
           sep = "border=\"1\" sides=\"b\""
        values = {}
        for val in [("qiime2_type", "value"), ("qiime2_format", "value"), ("uploaded_artifact", "file")]:
            try:
                values[val[0]] = self.get_value(*val)
            except:
                pass
        if "qiime2_type" in values:
            htm += "<tr><td colspan=\"3\" %s><b><font point-size=\"18\">%s</font></b></td></tr>" % (sep, self.human_short(),)#values["qiime2_type"])
#        if "qiime2_format" in values:
#            htm += "<tr><td colspan=\"2\"><font point-size=\"14\">%s</font></td></tr>" % (values["qiime2_format"],)
        if "uploaded_artifact" in values:
            htm += "<tr><td colspan=\"3\"><font point-size=\"14\">Artifact Available</font></td></tr>"
#        htm += "<tr><td colspan=\"2\"><font point-size=\"14\">%s</font></td></tr>" % (str(getattr(self, self.id_field)),)
        if show_values and value_counts is None:
            val_counts = self.get_value_counts()[self.pk]
        elif show_values and value_counts:
            val_counts = value_counts
        else:
            val_counts = {}
        if val_counts:
            htm += "<tr><td><i>Type</i></td><td><i>Count</i></td></tr>"
            for vtype, count in val_counts.items():
                htm += "<tr><td border=\"1\" bgcolor=\"#ffffff\">%s</td>" % (vtype.capitalize(),)
                htm += "<td border=\"1\" bgcolor=\"#ffffff\">%d</td></tr>" % (count,)
            if ('description' in val_counts) and (val_counts['description'] >= 0):
                descriptions = self.values.instance_of(apps.get_model("db.Description"))
                htm+="<tr><td colspan=\"2\">Description</td></tr>"
                for descrip in descriptions:
                    htm+="<tr><td border=\"1\" colspan=\"2\"><i>%s</i></td></tr>" % ("<BR/>".join(wrap(descrip.data.get().get_value(), width=70)),)
        htm += "</table>>"
        attrs = self.gv_node_style.copy()
        attrs["name"] = str(self.pk)
        attrs["label"] = htm
        attrs["fontname"] = "Arial"
        attrs["href"] = reverse(self.base_name + "_detail",
                                kwargs={self.base_name+"_id":self.pk})
        if not highlight:
            col = colour.Color(attrs["fillcolor"])
        else:
            black= colour.Color('black')
            col = colour.Color(attrs["fillcolor"])
            col = list(col.range_to(black, 10))[1]
            attrs['penwidth'] = "3"
        attrs['fillcolor'] = col.hex_l
        return attrs

    def simple_provenance_graph(self):
        dot = gv.Digraph("provenance", format='svg')
        dot.graph_attr.update(compound='true')
        dot.graph_attr.update(rankdir="LR")
        #dot.graph_attr.update(size="10,10!")
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
#        samplegraph = gv.Digraph("cluster0")
#        sample_name = None
#        nsamples = self.samples.count()
#        for sample in self.samples.all()[0:3]:
#            attrs = sample.get_node_attrs(show_values=False)
#            attrs['name'] = "S%d" % (sample.pk,)
#            attrs['fontname'] = 'Arial'
#            sample_name = attrs['name']
#            samplegraph.node(**attrs)
#        if nsamples>3:
#            nmore = nsamples - 3
#            attrs = sample.get_node_attrs(highlight=False, show_values=False)
#            attrs['fontname'] = 'Arial'
#            attrs['label'] = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr><tr><td colspan=\"3\"><b>%d more...</b></td></tr></table>>" % ("SAMPLE",nmore)
#            attrs['name'] = "SX"
#            samplegraph.node(**attrs)
#        featuregraph = gv.Digraph("cluster1")
#        feature_name = None
#        nfeatures = self.features.count()
#        for feature in self.features.all()[0:3]:
#            attrs = feature.get_node_attrs(show_values=False)
#            attrs['name'] = "F%d" % (feature.pk,)
#            attrs['fontname'] = 'Arial'
#            feature_name = attrs['name']
#            featuregraph.node(**attrs)
#        if nfeatures>3:
#            nmore = nfeatures - 3
#            attrs = feature.get_node_attrs(highlight=False, show_values=False)
#            attrs['fontname'] = 'Arial'
#            attrs['label'] = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr><tr><td colspan=\"3\"><b>%d more...</b></td></tr></table>>" % ("FEATURE",nmore)
#            attrs['name'] = "FX"
#            featuregraph.node(**attrs)
#        dot.subgraph(featuregraph)
#        dot.subgraph(samplegraph)
#        if sample_name is not None:
#            dot.edge(sample_name, "R", ltail="cluster0")
#        if feature_name is not None:
#            dot.edge(feature_name, "R", ltail="cluster1")
        return dot
