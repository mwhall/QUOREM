from collections import defaultdict, OrderedDict
from textwrap import fill, wrap
import string

from django import forms
from django.forms import ModelForm 
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import UpdateView, CreateView
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.shortcuts import render
from combomethod import combomethod

import pandas as pd
import graphviz as gv
import colour

from quorem.wiki import refresh_automated_report

from django_pandas.managers import DataFrameManager
import django_pandas as dpd

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

    description = "The base class for all Objects in QUOREM"

    search_fields = []
    grid_fields = [id_field]
    allowed_filter_fields = OrderedDict()

    gv_node_style = {}
    node_height = 2
    node_width = 3

    search_vector = SearchVectorField(blank=True,null=True)

#    objects = DataFrameManager()
    content_type_id_to_name = {}

    class Meta:
        abstract = True
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        return self.get_detail_link()

    @classmethod
    def _update_content_type_cache(cls):
        cls.content_type_id_to_name = dict(ContentType.objects.values_list("id","model"))

    def qs(self):
        return self._meta.model.objects.filter(pk=self.pk)

    def get_str_fields(self, measures=False, objects=True):
        field_values = defaultdict(list)
        for val in self.values.all():
            bn = val.base_name
            if (not measures) and (bn == "measure"):
                continue
            field_name = val.name+"_"+bn
            if objects:
                field_values[field_name].append(val.data)
            else:
                field_values[field_name].append(str(val.data.get_value()))
        return field_values

    @classmethod
    def get_all_value_fields(cls):
        val_fields = defaultdict(set)
        objs = apps.get_model("db.DataSignature").objects.filter(object_counts__results__gt=0).values_list("value_type","name").distinct()
        for vpk, name in objs:
            val_fields[ContentType.objects.get_for_id(vpk).model_class().base_name].add(name)
        return val_fields

    def get_value_fields(self):
        field_values = defaultdict(set)
        data_pk = self.values.values_list("data__pk", flat=True)
        for Val in apps.get_model("db.Value").get_value_types():
            vals = Val.objects.filter(data__pk__in=data_pk)
            for name in vals.values_list("signature__name", flat=True):
                field_values[Val.base_name].add(name)
        return field_values

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

    def get_value(self, name, value_type=None):
        if value_type is not None:
            value_type = apps.get_model("db.Value").get_value_types(type_name=value_type)
        else:
            value_type = apps.get_model("db.Value")
        return self.values.instance_of(value_type).get(signature__name=name).data.get().get_value()

    def has_value(self, name, value_type=None):
        if value_type is not None:
            value_type = apps.get_model("db.Value").get_value_types(type_name=value_type)
        else:
            value_type = apps.get_model("db.Value")
        return self.values.instance_of(value_type).filter(signature__name=name).exists()

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
            if field.is_relation and (field.related_model in Object.get_object_types()) and \
            ( (field_name == field.related_model.base_name) or (field_name == field.related_model.plural_name)):
                return (field.name, field.many_to_many) if m2m else field.name
            elif not field.is_relation and (field.name == field_name):
                return (field.name, False) if m2m else field.name
        return (None, None) if m2m else None

    @classmethod
    def _parse_kwargs(cls, value_kwargs=False, **kwargs):
        # Parses input arguments from the user-friendly IO fields into API-friendly keyword fields
        object_types = Object.get_object_types()
        object_ids = {Obj.plural_name: [] for Obj in object_types}
        create_kwargs = {Obj.plural_name: {} for Obj in object_types}
        update_kwargs = {Obj.plural_name: {} for Obj in object_types}
        # Rough save order for getting existence straightened out #TODO: Introspect this through related fields
        object_order = [apps.get_model("db.Investigation"),
                        apps.get_model("db.Step"),
                        apps.get_model("db.Sample"),
                        apps.get_model("db.Feature"),
                        apps.get_model("db.Process"),
                        apps.get_model("db.Analysis"),
                        apps.get_model("db.Result")]
        object_headings = [y for x in [x.column_headings() for x in object_order] for y in x]
        for column_heading, required in object_headings:
            keys = [x for x in kwargs if x.startswith(column_heading)]
            vals = [kwargs[x] for x in kwargs if x.startswith(column_heading)]
            base_type = Object.get_object_types(type_name=column_heading.split("_")[0])
            field, m2m = base_type.heading_to_field(column_heading, m2m=True)
            if field:
                if field in kwargs:
                    keys.append(field)
                if len(keys) == 0:
                    continue
                if field == base_type.id_field:
                    for k in keys:
                        object_ids[base_type.plural_name] = vals
                else:
                    if base_type.relational_field(field):
                        data = base_type._meta.get_field(field).related_model.objects.filter(name__in=vals)
                        if not data.exists():
                            continue #Skip it. TODO: indicate it's not found somehow, so we don't have to iterate twice (once for create, once for update) and can just add it later
                        if not m2m:
                            data = data.first()
                    if required and (field != "upstream"):
                        create_kwargs[base_type.plural_name][field] = data
                    if not required or (field == base_type.id_field) or (field=="upstream"):
                        update_kwargs[base_type.plural_name][field] = data
        object_ids = {x: object_ids[x] for x in object_ids if object_ids[x]}
        create_kwargs = {x: create_kwargs[x] for x in create_kwargs if create_kwargs[x] != {}}
        update_kwargs = {x: update_kwargs[x] for x in update_kwargs if update_kwargs[x] != {}}
        return object_ids, create_kwargs, update_kwargs

    def iter_values_str(self):
        vals=self.values.values("signature__name", "data__pk", "signature__value_type__model")
        out_str = ""
        for val in vals:
            try:
                data = apps.get_model("db.Data").objects.get(pk=val['data__pk'])
            except:
                pass
            yield {"name": val['signature__name'],
                   "data": str(data),
                   "type": val['signature__value_type__model'].capitalize()}

    def _make_accordion(self, name, data):
        #Data must be in format
        #{"groupName": ("groupLabel", "groupContent/HTML")}
        accordion_html = format_html('<div class="accordion" id="{}Accordion">', name)
        for group_label in data:
            accordion_html += '<div class="card">'
            accordion_html += format_html('<div class="card-header" id="heading{}">', group_label)
            accordion_html += '<h2 class="mb-0">'
            accordion_html += format_html('<button class="btn btn-link" type="button" data-toggle="collapse" \
                                           data-target="#collapse{}" aria-expanded="false" aria-controls="collapse{}">',
                                          group_label, group_label)
            accordion_html += mark_safe(data[group_label]["heading"])
            accordion_html += '</button></h2></div>'
            accordion_html += format_html('<div id="collapse{}" class="collapse" aria-labelledby="heading{}" data-parent="#{}Accordion">', group_label, group_label, name)
            accordion_html += '<div class="card-body">'
            accordion_html += mark_safe(data[group_label]["content"])
            accordion_html += '</div></div></div>'
        accordion_html += "</div>"
        return accordion_html

    def html_values(self):
        value_type_options = self.values.values_list("signature__value_type__model",flat=True).distinct()
        value_counts = self.get_value_counts()[self.pk]
        accordions = {x: {"heading": "%s (%d)" % (x.capitalize(), value_counts[x]), "content": ""} for x in value_type_options}
        for value_str in self.iter_values_str():
            accordions[value_str["type"].lower()]["content"] += format_html("{}: {}</BR>", value_str["name"],
                                                                                           value_str["data"])
        return self._make_accordion("value", accordions)

    def bootstrap_card(self):
        descriptions = self.values.instance_of(apps.get_model("db.Description"))
        html = "<div class=\"card bg-light mb-3 border-bottom\" style=\"max-width: 100%;\">"
        html +=     "<div class=\"card-header\">%s</div>" % (self.base_name.capitalize(), )
        html +=     "<div class=\"card-body\">"
        html +=       "<h5 class=\"card-title\">%s</h5>" % (self.get_detail_link(),)
        html += "<p class=\"card-text\">"
        for descrip in descriptions:
            html += descrip.data.get().get_value()
        html +=       "</p>"
        html +=     "</div>"
        html +=   "</div>"
        return html

    @combomethod
    def get_value_counts(receiver, queryset=None):
        if type(receiver) == models.base.ModelBase:
            manager = receiver.objects
            if queryset == None:
                queryset = manager.all()
        else:
            manager = receiver._meta.model.objects
            if queryset == None:
                queryset = manager.filter(pk=receiver.pk)
        val_counts = queryset.annotate(vtype_count=models.Count("values__polymorphic_ctype_id")).values_list("pk","values__polymorphic_ctype_id","vtype_count")
        type_counts = defaultdict(dict)
        if not receiver.content_type_id_to_name:
            receiver._update_content_type_cache()
        for pk, cid, count in val_counts:
            if cid:
                type_counts[pk][receiver.content_type_id_to_name[cid]] = count
        return type_counts

    @combomethod
    def dataframe(receiver, wide=False, additional_fields=None, **kwargs):
        if receiver.plural_name not in kwargs:
            if type(receiver) == models.base.ModelBase:
                kwargs[receiver.plural_name] = receiver.objects.all()
            else:
                kwargs[receiver.plural_name] = receiver.qs()
        fieldnames = ["signature__name", "signature__value_type__model", "data"]
        if additional_fields:
            fieldnames += additional_fields
        objs_kwargs = [x.plural_name for x in Object.get_object_types() if x.plural_name in kwargs]
        fkwargs = {}
        #Deal with the case where we're given ints (PKs), strings (names), or other (likely QuerySets)
        for obj in objs_kwargs:
            if type(kwargs[obj][0]) == int:
                kw = obj+"__in"
            
            elif type(kwargs[obj][0]) == str:
                kw = obj+"__name__in"
            else:
                kw = obj+"__in"
            fkwargs[kw] = kwargs[obj]
        if 'value_names' in kwargs:
            fkwargs['signature__name__in'] = kwargs['value_names']
        if 'only_types' in kwargs:
            only = [ContentType.objects.get_for_model(x) for x in kwargs['only_types']]
            fkwargs['signature__value_type__model__in'] = only
        objs_names = [x + "__name" for x in objs_kwargs]
        fieldnames += objs_names
        vals = apps.get_model("db.Value").objects.filter(**fkwargs)
    #    if 'exclude_types' in kwargs:
    #        exclude= {'signature__name__in': kwargs['exclude_types']}
    #        vals = vals.exclude(**exclude)
        df = dpd.io.read_frame(vals, fieldnames=fieldnames, index_col=objs_names[0])
        data = apps.get_model("db.Data").objects.filter(pk__in=df["data"]).get_real_instances()
        values = {x.pk: x.get_value() for x in data}
        df["data"] = df["data"].apply(lambda x: values[x])
        if wide:
            df = df.pivot_table(values="data",columns="signature__name", index=objs_names, aggfunc=lambda x: x)
            df.columns = df.columns.rename("value_name")
        name_map = {"signature__name": "value_name",
                          "signature__value_type__model": "value_type",
                          "data": "value_data"}
        name_map.update({x+"__name": x+"_name" for x in objs_kwargs})
        df.rename(mapper=name_map, axis=1, inplace=True)
        if not wide:
            df.index = df.index.rename(objs_kwargs[0]+"_name")
        return df

    @combomethod
    def info(receiver):
        out_str = "Object type name: %s\n" % (receiver.base_name.capitalize(),)
        out_str += receiver.description + "\n"
        if type(receiver) == models.base.ModelBase:
            if receiver.has_upstream:
                out_str += "%s have upstream/downstream links to other %s\n" % (receiver.plural_name.capitalize(), receiver.plural_name)
            out_str += "There are %d %s in this QUOREM instance\n" % (receiver.objects.count(), receiver.plural_name)
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
        req_headings = [col for col, req in cls.column_headings() if req]
        req_fields = []
        all_headings = [col for col, req in cls.column_headings()]
        create_kwargs = {}
        for heading in req_headings:
            field, m2m = cls.heading_to_field(heading, m2m=True)
            req_fields.append(field)
            # ID is provided by name so we can skip it here
            if field and (field != cls.id_field):
                if field in kwargs:
                    key = field
                elif heading in kwargs:
                    key = heading
                else:
                    raise ValueError("Required heading %s (or argument '%s') not found when creating %s" % (heading, field, cls.base_name.capitalize()))
                create_kwargs[field] = kwargs[key]
        obj = cls.objects.create(name=name, **create_kwargs)
        return cls.objects.filter(pk=obj.pk)

    def update(self, **kwargs):
        field_names = [x.name for x in self._meta.get_fields()]
        save_required = False
        for arg in kwargs:
            if arg in field_names:
                field = arg
            else:
                field = self.heading_to_field(arg)
            if not field:
                continue
            data = kwargs[arg]
            if field == "upstream":
                update_upstream = False
                for obj in data:
                    if obj not in self.upstream.all():
                        update_upstream=True
                if not update_upstream:
                    continue
            Field = getattr(self, field)
            if hasattr(Field, 'add'):
                print("Adding to field '%s' data '%s'" % (field, str(data)))
                Field.add(*data)
            else:
                setattr(self, field, data)
                save_required = True
            if field == "upstream":
                for ref_obj in data:
                    self.all_upstream.add(ref_obj)
                    upstream_qs = ref_obj.all_upstream.all()
                    downstream_qs = self.all_downstream.all()
                    self.all_upstream.add(*upstream_qs)
                    ref_obj.all_downstream.add(*downstream_qs)
                    ref_obj.save()
                    for down_obj in downstream_qs:
                        for up_obj in upstream_qs:
                            down_obj.all_upstream.add(up_obj)
                        down_obj.save()
        if save_required:
            self.save()

    @classmethod
    def get_or_create(cls, name, **kwargs):
        objs = cls.get(name)
        if not objs.exists():
            try:
               objs = cls.create(name, **kwargs)
            except:
               raise
        return cls.objects.filter(pk__in=objs)

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
    def get_create_view(cls, as_view=False):
        class ObjectCreateView(CreateView):
            model = cls
            fields = [cls.heading_to_field(x[0]) for x in cls.column_headings() if x[1]]
            template_name = "create.htm"
            def get_context_data(self,*args, **kwargs):
                context = super().get_context_data(*args,**kwargs)
                context['base_name'] = cls.base_name
                return context
        if as_view:
            return ObjectCreateView.as_view()
        return ObjectCreateView

    @classmethod
    def get_update_view(cls, as_view=False):
        class ObjectUpdateView(UpdateView):
            pk_url_kwarg = cls.base_name + '_id'
            form = cls.get_crud_form()
            template_name = "core/custom_cbv_edit_inline.htm"
            def get_heading(self):
                return "Update %s" % (cls.base_name.capitalize(),)
            def get_bs_form_opts(self):
                return {'submit_text': 'Save %s' % (cls.base_name.capitalize(),)}
            def get_success_url(self):
                return reverse('%s_detail' % (cls.base_name,),
                               kwargs = {'%s_id' % (cls.base_name,): self.object.pk})

        ObjectUpdateView.__module__ = cls.base_name
        ObjectUpdateView.__name__ = cls.__name__
        ObjectUpdateView.__qualname__ = ObjectUpdateView.__name__
        if as_view:
            return ObjectUpdateView.as_view()
        else:
            return ObjectUpdateView

    @classmethod
    def get_display_form(cls):
#        # Causes issues if these are above before a DB exists
        class DisplayForm(ModelForm):
#            value_accordion = forms.CharField(label="Values")
##            node = forms.CharField(widget=DisplayText())
#            if cls.has_upstream:
#                graph = forms.CharField()
            class Meta:
                model = cls
                exclude = ['search_vector', 'values']
#                if cls.has_upstream:
#                    exclude += ['all_upstream']
#            def __init__(self, *args, **kwargs):
#                if kwargs.get('instance'):
#                    if 'initial' in kwargs:
#                        initial = kwargs['initial']
#                    else:
#                        kwargs['initial'] = OrderedDict()
#                        initial = kwargs['initial']
##                    initial['node'] = mark_safe(kwargs['instance'].get_node(show_values=True).pipe().decode().replace("\n",""))
#                    initial['value_accordion'] = mark_safe(kwargs['instance'].html_values())
#                    if cls.has_upstream:
#                        initial['graph'] = mark_safe(kwargs['instance'].get_stream_graph().pipe().decode().replace("<svg ", "<svg class=\"img-fluid\" ").replace("\n",""))
#                super().__init__(*args, **kwargs)
        return DisplayForm

    @classmethod
    def get_detail_view(cls, as_view=False):
        class ObjectDetailView(DetailView):
            pk_url_kwarg = cls.base_name + '_id'
            form = cls.get_display_form()
            queryset = cls.objects.all()
            template_name = "detail.htm"
            def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                #Add to context dict to make available in template
                obj = self.get_object()
                if len(obj.get_value_counts())>0:
                    context['values_html'] = mark_safe(self.get_object().html_values())
                return context

        ObjectDetailView.__module__ = cls.base_name
        ObjectDetailView.__name__ = cls.__name__
        ObjectDetailView.__qualname__ = DetailView.__name__
        if as_view:
            return ObjectDetailView.as_view()
        else:
            return ObjectDetailView

#    @classmethod
#    def get_list_view(cls):
#        base_name = cls.base_name
#        def object_list_view(request):
#            object_list = cls.objects.all()
#            return render(request, 'list.htm')
##        class ObjectListView(ListView):
##            model = cls
##            paginate_by = 20
##            template_name = "list.htm"
##            def get_context_data(self, **kwargs):
##                context = super().get_context_data(**kwargs)
##                context['list_url'] = base_name+"_all"
##                context['base_name'] = base_name
##                return context
#        return object_list_view
#
    @classmethod
    def get_filters(cls):
        return OrderedDict()

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

    def related_samples_count(self, upstream=False):
        return self.related_samples(upstream).count()

    def related_processes(self, upstream=False):
        processes = apps.get_model("db", "Process").objects.filter(pk__in=self.related_steps(upstream=upstream).values("processes").distinct())
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_features(self):
        return apps.get_model("db", "Feature").objects.filter(samples__in=self.related_samples()).distinct()

    def related_features_count(self):
        return self.related_features().count()

    def related_steps(self, upstream=False):
        # Return the source_step for each sample
        steps = apps.get_model("db", "Step").objects.filter(pk__in=self.related_samples(upstream=upstream).values("source_step").distinct())
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_analyses(self):
        return apps.get_model("db", "Analysis").objects.filter(results__in=self.related_results()).distinct()
    def related_analysis_badges(self):
        html_val = ""
        for anal in self.related_analyses():
            html_val += '<a class="badge badge-secondary" href="/analysis/%d/">%s</a>&nbsp;' % (anal.pk, anal.name,)
        return mark_safe(html_val)

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

    def get_absolute_url(self):
        return "/%s/%i/" % (self.base_name, self.pk)

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

    def get_update_link(self):
        kwargs = {}
        lookup = self.base_name + "_update"
        kwargs[self.base_name + "_id"] = self.pk
        return reverse(lookup, kwargs=kwargs)

    def get_node_attrs(self, show_values=True, highlight=False, value_counts=None):
        htm = "<<table border=\"0\"><tr><td colspan=\"2\"><b>%s</b></td></tr>" % (self.base_name.upper(),)
        if not show_values:
           sep = ""
        else:
           sep = "border=\"1\" sides=\"b\""
        htm += "<tr><td colspan=\"2\" %s><b><font point-size=\"18\">%s</font></b></td></tr>" % (sep, str(getattr(self, self.id_field)))
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

    def get_node(self, show_values=True, highlight=False, format='svg'):
        dot = gv.Digraph("nodegraph_%s_%d" % (self.base_name, self.pk), format=format)
        #dot.attr(size="%d,%d!" % (self.node_height, self.node_width))
        dot.node(**self.get_node_attrs(show_values=show_values, highlight=highlight))
        return dot

    def get_stream_graph(self, show_values=False, format='svg'):
        dot = gv.Digraph("streamgraph_%s_%d" % (self.base_name, self.pk), format=format)
        origin = self
        dot.node(**origin.get_node_attrs(show_values=show_values, highlight=True))
        edges = set()
        for us_pk in origin.upstream.values_list("pk", flat=True):
            edges.add((str(us_pk), str(origin.pk)))
        for ds_pk in origin.downstream.values_list("pk", flat=True):
            edges.add((str(origin.pk), str(ds_pk)))
        upstream = origin.all_upstream.prefetch_related("upstream", "downstream")
        downstream = origin.all_downstream.prefetch_related("upstream", "downstream")
        both = upstream | downstream
        nnodes = len(both)+1
        all_pks = both.values_list("pk",flat=True)
        for obj in both:
            attrs = obj.get_node_attrs(show_values=show_values, value_counts=obj.get_value_counts()[obj.pk])
            dot.node(**attrs)
            for us_pk in obj.upstream.values_list("pk", flat=True):
                if us_pk in all_pks:
                    edges.add((str(us_pk), str(obj.pk)))
            for ds_pk in obj.downstream.values_list("pk", flat=True):
                if ds_pk in all_pks:
                    edges.add((str(obj.pk), str(ds_pk)))
        dot.edges(list(edges))
#        dim = max(14,int(nnodes/2.0))
#        dim = min(dim, 10)
#        dot.attr(size="%d,%d!" % (dim,2*dim))
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
