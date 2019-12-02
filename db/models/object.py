from collections import defaultdict

from django import forms
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.apps import apps

from django_jinja_knockout.forms import BootstrapModelForm, DisplayModelMetaclass
from django_jinja_knockout.views import InlineDetailView
from django_jinja_knockout.widgets import DisplayText

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

from combomethod import combomethod

import pandas as pd
import graphviz as gv

from quorem.wiki import refresh_automated_report

User = get_user_model()

##################################
# Generic Base Class for Objects #
#

class Object(models.Model):
    base_name = "object"
    plural_name = "objects"
    id_field = "name"
    has_upstream = False
    search_set = None

    description = "The base class for all Objects in QUOR'em"

    gv_node_style = {}

    search_vector = SearchVectorField(blank=True,null=True)

    class Meta:
        abstract = True
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        return self.get_detail_link()

    @classmethod
    def id_fields(cls):
        return ["%s_%s" % (x.base_name, x.id_field) for x in cls.get_object_types()]

    @combomethod
    def column_headings(receiver):
        object_list = Object.get_object_types()
        object_names = [Obj.base_name for Obj in object_list]
        if receiver.base_name == "object":
            return_list = object_list
        else:
            return_list = [receiver]
        headings = set()
        for Obj in return_list:
            #Defines the column headings for this Object's input scheme
            headings.add(*[("%s_%s" % (Obj.base_name, Obj.id_field), True)])
            if Obj.has_upstream:
                headings.add(("%s_upstream" % (Obj.base_name,), False))
            # Returns tuples of the field name, from model, and to model
            for field in Obj._meta.get_fields():
                if field.is_relation and \
                   (field.related_model != Obj) and \
                   (field.related_model in object_list):
                    headings.add(("%s_%s" % (Obj.base_name, field.related_model.base_name), 
                                             not (hasattr(field, "blank") and field.blank) and field.concrete))
        return list(headings)

    @classmethod
    def relational_field(cls, field):
        return cls._meta.get_field(field).is_relation

    @classmethod
    def heading_to_field(cls, heading, m2m=False):
        if "_" in heading:
            field_name = heading.split("_")[1]
        else:
            field_name = heading
        if field_name == "upstream":
            return (field_name, True) if m2m else field_name
        for field in cls._meta.get_fields():
            if field.name == "id":
                continue #skip database id field
            if field.is_relation and (field.related_model in Object.get_object_types()) and \
            ( (field_name == field.related_model.base_name) or (field_name == field.related_model.plural_name)):
                return (field.name, field.many_to_many) if m2m else field.name
            elif not field.is_relation and (field.name == field_name):
                return (field.name, False) if m2m else field.name
        return (None, None) if m2m else None

    @classmethod
    def _parse_kwargs(cls, value_kwargs=False, **kwargs):
        # Parses input arguments from the user-friendly IO fields into API-friendly keyword fields
        object_ids = {Obj.plural_name: [] for Obj in Object.get_object_types()}
        object_kwargs = {Obj.plural_name: {} for Obj in Object.get_object_types()}
        for column_heading, required in Object.column_headings():
            headings = [x for x in kwargs if x.startswith(column_heading)]
            if not headings:
                continue
            heading = headings[0].split(".")[0]
            base_type = Object.get_object_types(type_name=heading.split("_")[0])
            field, m2m = base_type.heading_to_field(heading, m2m=True)
            if field:
                if field == base_type.id_field:
                    for h in headings:
                        object_ids[base_type.plural_name].append(kwargs[h])
                else:
                    for h in headings:
                        if base_type.relational_field(field):
                            related_kwargs = kwargs.copy()
                            related_kwargs = {base_type.heading_to_field(x): y for x,y in related_kwargs.items() if x in [x[0] for x in base_type.column_headings()]}
                            for key, val in related_kwargs.items():
                                if base_type.relational_field(key):
                                    relfield = base_type._meta.get_field(key)
                                    if relfield.many_to_many:
                                        related_kwargs[key] = relfield.related_model.get_or_create(name=val)
                                    else:
                                        print("Hmmmmmmm")
                                        related_kwargs[key] = relfield.related_model.get_or_create(name=val).first()
                                        print("Made it through")
                            print(related_kwargs)
                            data = base_type._meta.get_field(field).related_model.get_or_create(**related_kwargs)
                            print("Made it again")
                        else:
                            data = kwargs[h]
                        object_kwargs[base_type.plural_name][field] = data
        object_ids = {x: object_ids[x] for x in object_ids if object_ids[x]}
        object_kwargs = {x: object_kwargs[x] for x in object_kwargs if object_kwargs[x] != {}}
        return object_ids, object_kwargs

    @combomethod
    def info(receiver):
        out_str = "Object type name: %s\n" % (receiver.base_name.capitalize(),)
        out_str += receiver.description + "\n"
        if type(receiver) == models.base.ModelBase:
            if receiver.has_upstream:
                out_str += "%s have upstream/downstream links to other %s\n" % (receiver.plural_name.capitalize(), receiver.plural_name)
            out_str += "There are %d %s in this QUOR'em instance\n" % (receiver.objects.count(), receiver.plural_name)
        else:
            out_str += "There are %d %s upstream of this one, and %d %s downstream of this one\n" % (receiver.all_upstream.count(), receiver.plural_name, receiver.all_downstream.count(), receiver.plural_name)
            value_counts = ", ".join(["%d %s" % (vtype.objects.filter(pk__in=receiver.values.all()).count(), vtype.plural_name) for vtype in apps.get_model('db.Value').get_value_types()])
            out_str += "It has %d Values (%s)\n" % (receiver.values.count(), value_counts)
        return out_str

    @classmethod
    def get(cls, name):
        return cls.objects.filter(name=name)

    @classmethod
    def create(cls, name, **kwargs):
        # Check for the required fields:
        req_fields = [col for col, req in cls.column_headings() if req]
        for heading in req_fields:
            field = cls.heading_to_field(heading)
            if (heading in kwargs) and field:
                kwargs[field] = kwargs[heading]
                del kwargs[heading]
            if field == 'name':
                continue
            elif field not in kwargs:
                raise ValueError("Required field %s not found when creating %s" % (field, cls.base_name.capitalize()))
        obj = cls.objects.create(name=name, **kwargs)
        obj.update(**kwargs)
        return cls.objects.filter(pk=obj.pk)

    def update(self, **kwargs):
        for heading in kwargs:
            field, m2m = self.heading_to_field(heading, m2m=True)
            if field:
                data = kwargs[heading]
                field = getattr(self, field)
                if m2m:
                    field.add(*data)
                else:
                    field = data
        self.save()

    @classmethod
    def get_or_create(cls, name, **kwargs):
        try:
            obj = cls.get(name)
        except:
            obj = None
        if not obj or (hasattr(obj, "exists") and not obj.exists()):
            try:
               obj = cls.create(name, **kwargs)
            except:
                print(name)
                print(kwargs)
                raise
        return cls.objects.filter(pk__in=obj.values("pk"))


    @classmethod
    def linkable(cls, value_name):
        # All Values can be linked to the base class
        # and to everything else by default
        # Override this for white/blacklist
        value_type = apps.get_model("db.Value").get_value_types(type_name=value_name)
        return cls.plural_name in value_type.linkable_objects

    @classmethod
    def get_object_types(cls, type_name=None):
        if type_name == None:
            return cls.__subclasses__()
        else:
            for Obj in cls.__subclasses__():
                if (type_name.lower() == Obj.base_name) or (type_name.lower() == Obj.plural_name):
                    return Obj
            raise ValueError("Unknown Object %s" % (type_name,))

    @classmethod
    def get_queryset(cls, data):
        #data is a dict with {field_name: [name1,...],}
        # and uuid for results, id for all
        if (not data):
            return cls._meta.model.objects.none()
        kwargs = {}
        for id_field in [cls.id_field, "id"]:
            field = "%s_%s" % (cls.base_name, id_field)
            if field in data:
                if type(data[field]) == list:
                    kwargs[id_field + "__in"] = data[field]
                else:
                    kwargs[id_field + "__in"] = [data[field]]
        if not kwargs:
            return cls._meta.model.objects.none()
        return cls._meta.model.objects.filter(**kwargs)

    @classmethod
    def get_display_form(cls):
        class DisplayForm(BootstrapModelForm,
                          metaclass=DisplayModelMetaclass):
            node = forms.CharField(max_length=4096, widget=DisplayText())
            if cls.has_upstream:
                graph = forms.CharField(max_length=4096, widget=DisplayText())
            class Meta:
                model = cls
                exclude = ['search_vector', 'values']
                if cls.has_upstream:
                    exclude += ['all_upstream']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    initial=kwargs.setdefault('initial',{})
                    initial['node'] = mark_safe(kwargs['instance'].get_node(values=True).pipe().decode().replace("\n",""))
                    if cls.has_upstream:
                        initial['graph'] = mark_safe(kwargs['instance'].get_stream_graph().pipe().decode().replace("\n",""))
                super().__init__(*args, **kwargs)
        return DisplayForm

    @classmethod
    def get_detail_view(cls, as_view=False):
        class DetailView(InlineDetailView):
            pk_url_kwarg = cls.base_name + '_id'
            form = cls.get_display_form()
            def get_heading(self):
                return ""
        DetailView.__module__ = cls.base_name
        DetailView.__name__ = cls.__name__
        DetailView.__qualname__ = DetailView.__name__
        if as_view:
            return DetailView.as_view()
        else:
            return DetailView

    def get_upstream_values(self):
        if not self.has_upstream:
            return apps.get_model("db", "Value").objects.none()
        upval_pks = self.all_upstream.prefetch_related("values")
        return apps.get_model("db", "Value").objects.filter(pk__in=upval_pks.values("values"))

    # Default search methods, using only internal methods
    # At least one of these has to be overridden
    def related_samples(self, upstream=False):
        samples = apps.get_model("db", "Sample").objects.filter(source_step__in=self.related_steps(upstream=upstream)).distinct()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=samples.values("all_upstream").distinct())
        return samples

    def related_processes(self, upstream=False):
        processes = apps.get_model("db", "Process").objects.filter(pk__in=self.related_steps(upstream=upstream).values("processes").distinct())
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_features(self):
        return apps.get_model("db", "Feature").objects.filter(samples__in=self.related_samples()).distinct()

    def related_steps(self, upstream=False):
        # Return the source_step for each sample
        steps = apps.get_model("db", "Step").objects.filter(pk__in=self.related_samples(upstream=upstream).values("source_step").distinct())
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_analyses(self):
        return apps.get_model("db", "Analysis").objects.filter(results__in=self.related_results()).distinct()

    def related_results(self, upstream=False):
        results = apps.get_model("db", "Result").objects.filter(samples__in=self.related_samples(upstream=upstream)).distinct()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

    def related_investigations(self):
        return apps.get_model("db", "Investigation").objects.filter(samples__in=self.related_samples()).distinct()

    # Generic wrapper so we can get objects by string name instead of use getattr or something
    def related_objects(self, object_name, upstream=False):
        name_map = {"samples": self.related_samples,
                    "features": self.related_features,
                    "steps": self.related_steps,
                    "processes": self.related_processes,
                    "analyses": self.related_analyses,
                    "results": self.related_results,
                    "investigations": self.related_investigations}
        kwargs = {}
        if object_name in ["samples", "steps", "processes", "results"]:
            kwargs["upstream"] = upstream
        return name_map[object_name](**kwargs)

    @combomethod
    def get_detail_link(receiver):
        kwargs = {}
        if type(receiver) == models.base.ModelBase:
            lookup = receiver.base_name + "_all"
            name = "All Steps"
        else:
            lookup = receiver.base_name + "_detail"
            kwargs[receiver.base_name + "_id"] = receiver.pk
            name = getattr(receiver, receiver.id_field)
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(lookup,
                                 kwargs=kwargs)}),
                                 name))

    def get_node_attrs(self, values=True):
        htm = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr>" % (self.base_name.upper(),)
        if not values:
           sep = ""
        else:
           sep = "border=\"1\" sides=\"b\""
        htm += "<tr><td colspan=\"3\" %s><b><font point-size=\"18\">%s</font></b></td></tr>" % (sep, str(getattr(self, self.id_field)))
        if values:
            val_names = list(self.values.all().values_list("name","signature__value_type").distinct())
            val_counts = []
            for name, type in val_names:
                count = self.values.filter(name=name).count()
                val_counts.append((name, type, count)) 
            if len(val_counts) > 0:
                htm += "<tr><td><i>Values Present</i></td><td><i>Type</i></td><td><i>Count</i></td></tr>"
                for name, type, count in val_counts:
                    htm += "<tr><td border=\"1\" bgcolor=\"#ffffff\">%s</td>" % (name,)
                    htm += "<td border=\"1\" bgcolor=\"#ffffff\">%s</td>" % (type,)
                    htm += "<td border=\"1\" bgcolor=\"#ffffff\">%d</td></tr>" % (count,)
        htm += "</table>>"
        attrs = self.gv_node_style
        attrs["name"] = str(self.pk)
        attrs["label"] = htm
        attrs["fontname"] = "FreeSans"
        attrs["href"] = reverse(self.base_name + "_detail", 
                                kwargs={self.base_name+"_id":self.pk})
        return attrs

    def get_node(self, values=True, format='svg'):
        dot = gv.Digraph("nodegraph_%s_%d" % (self.base_name, self.pk), format=format)
        dot.attr(size="4,4!")
        dot.node(**self.get_node_attrs(values=values))
        return dot

    def get_stream_graph(self, values=False, format='svg'):
        dot = gv.Digraph("streamgraph_%s_%d" % (self.base_name, self.pk), format=format)
        origin = self
        dot.node(**origin.get_node_attrs(values=values))
        edges = set()
        for us in origin.upstream.all():
            edges.add((str(us.pk), str(origin.pk)))
        for ds in origin.downstream.all():
            edges.add((str(origin.pk), str(ds.pk)))
        upstream = origin.all_upstream.prefetch_related("upstream", "downstream")
        downstream = origin.all_downstream.prefetch_related("upstream", "downstream")
        both = upstream | downstream
        nnodes = len(both)+1
        for obj in both:
            attrs = obj.get_node_attrs(values=values)
            dot.node(**attrs)
            for us in obj.upstream.all():
                if us in both:
                    edges.add((str(us.pk), str(obj.pk)))
            for ds in obj.downstream.all():
                if ds in both:
                    edges.add((str(obj.pk), str(ds.pk)))
        dot.edges(list(edges))
        dim = max(6,int(nnodes/2.0))
        dim = min(dim, 11)
        dot.attr(size="%d,%d!" % (dim,dim))
        return dot

##Function for search.
##Search returns a list of dicts. Get the models from the dicts.
def load_mixed_objects(dicts,model_keys):
    #dicts are expected to have 'pk', 'rank', 'type'
    to_fetch = {}
    for d in dicts:
        to_fetch.setdefault(d['otype'], set()).add(d['pk'])
    fetched = {}

    for key, model, ui_string in model_keys:
        #disregard the ui_string variable. It's for frontend convenience.
        ids = to_fetch.get(key) or []
        objects = model.objects.filter(pk__in=ids)
        for obj in objects:
            fetched[(key, obj.pk)] = obj
    #return the list in the same otder as dicts arg
    to_return = []
    for d in dicts:
        item = fetched.get((d['otype'], d['pk'])) or None
        if item:
                item.original_dict = d
        to_return.append(item)

    return to_return

