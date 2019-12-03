import cgi

from django.db import models
from django.apps import apps
from django import forms
from django_jinja_knockout.widgets import DisplayText

#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from db.models.object import Object
from django.utils.html import format_html, mark_safe

from django_jinja_knockout.forms import BootstrapModelForm, DisplayModelMetaclass

class Feature(Object):
    base_name = "feature"
    plural_name = "features"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ff5497'}
    node_height = 10
    node_width = 12

    description = "A Feature represents something that is being tracked across Samples, such as a taxonomic group, a functional gene, or a molecule"

    name = models.CharField(max_length=255, verbose_name="Name")
    samples = models.ManyToManyField('Sample', related_name='features', blank=True)

    annotations = models.ManyToManyField('Value', related_name='+', blank=True)
    values = models.ManyToManyField('Value', related_name="features", blank=True)

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector = (SearchVector('name', weight= 'A') +
                             SearchVector(StringAgg('annotations__str', delimiter=' '), weight='B'))
        )

    def related_samples(self, upstream=False):
        #SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_results(self, upstream=False):
        # SQL Depth: 2
        results = self.results.all()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

    def get_node_attrs(self, values=True):
        htm = "<<table border=\"0\"><tr><td colspan=\"2\"><b>%s</b></td></tr>" % (self.base_name.upper(),)
        if not values:
           sep = ""
        else:
           sep = "border=\"1\" sides=\"b\""
        htm += "<tr><td colspan=\"2\" %s><b><font point-size=\"18\">%s</font></b></td></tr>" % (sep, str(getattr(self, self.id_field)))
        if values:
            val_types = apps.get_model("db.Value").get_value_types()
            val_counts = []
            for vtype in val_types:
                count = self.values.instance_of(vtype).count()
                val_counts.append((vtype.base_name.capitalize(), count))
            if len(val_counts) > 0:
                htm += "<tr><td><i>Type</i></td><td><i>Count</i></td></tr>"
                for vtype, count in val_counts:
                    if count == 0:
                        continue
                    htm += "<tr><td border=\"1\" bgcolor=\"#ffffff\">%s</td>" % (vtype,)
                    htm += "<td border=\"1\" bgcolor=\"#ffffff\">%d</td></tr>" % (count,)
            data_types = self.annotations.values_list("signature__data_types", flat=True).distinct()
            annotations = []
            for data_type_pk in data_types:
                data_type = ContentType.objects.get_for_id(data_type_pk).model_class()
                annotations = data_type.objects.filter(pk__in=self.annotations.values("data")).values_list("value", flat=True)
            htm += "<tr><td colspan=\"2\"></td></tr>"
            htm += "<tr><td colspan=\"2\"><b>Annotations</b></td></tr>"
            for annotation in annotations:
                htm += "<tr><td colspan=\"2\">%s</td></tr>" % (cgi.escape(annotation),)
        htm += "</table>>"


        attrs = self.gv_node_style
        attrs["name"] = str(self.pk)
        attrs["label"] = htm
        attrs["fontname"] = "FreeSans"
        attrs["href"] = reverse(self.base_name + "_detail",
                                kwargs={self.base_name+"_id":self.pk})
        return attrs

    @classmethod
    def get_display_form(cls):
        class DisplayForm(BootstrapModelForm,
                          metaclass=DisplayModelMetaclass):
            node = forms.CharField(max_length=4096, widget=DisplayText())
            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'annotations']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    initial=kwargs.setdefault('initial',{})
                    initial['node'] = mark_safe(kwargs['instance'].get_node(values=True).pipe().decode().replace("\n",""))
                super().__init__(*args, **kwargs)
        return DisplayForm
    
    
