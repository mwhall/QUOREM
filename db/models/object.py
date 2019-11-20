from collections import defaultdict

from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.apps import apps

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
# Class Methods:
#  - .get_id_fields(): Get ID fields for this object
#  - .get_value_fields(): Get value fields for this object
#  - .get_queryset({"id_field":[id1,id2,...]}): Get a QuerySet from a list of IDs as values in a dictionary of with ID fields as keys
#  - .initialize({"field":[data1, data2,...]}): Validate data in dictionary and write only required fields, if not present in database
#  - .update({"field":[data1]}): writes the values for each field on each of the ID fields present in the dictionary, and makes the appropriate links
#
# Combo Methods:

class Object(models.Model):
    base_name = "object"
    plural_name = "objects"
    id_field = "name"
    has_upstream = False
    search_set = None

    gv_node_style = {}

    search_vector = SearchVectorField(blank=True,null=True)
    created_by = models.ForeignKey(User, on_delete="CASCADE",blank=True,null=True)

    class Meta:
        abstract = True
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        if not self._state.adding:
            self.search_set = self.__class__.objects.filter(pk=self.pk)

    def __str__(self):
        return self.name

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>',
                         flatatt({'href': reverse(self.base_name + '_detail',
                                 kwargs={self.base_name + '_id': self.pk})}),
                                 str(getattr(self, self.id_field))))

    @classmethod
    def get_id_fields(cls):
        return [cls.base_name + "_" + cls.id_field, cls.base_name + "_id"]

    @classmethod
    def get_value_fields(cls):
        return [cls.plural_name + "__" + cls.id_field, cls.plural_name + "__id"]

    @classmethod
    def get_queryset(cls, data):
        #data is a dict with {field_name: [name1,...],}
        # and uuid for results, id for all
        if (not data):
            return cls._meta.model.objects.none()
        kwargs = {}
        for id_field in [cls.id_field, "id"]:
            if cls.base_name + "_" + id_field in data:
                kwargs[id_field + "__in"] = data[cls.base_name + "_" + id_field]
        if not kwargs:
            return cls._meta.model.objects.none()
        return cls._meta.model.objects.filter(**kwargs)

    def get_values(self, name, value_type):
        return self.values.filter(name=name, value=value_type)

    def get_upstream_values(self, name, value_type):
        if not self.has_upstream:
            return apps.get_model("db", "Value").objects.none()
        return apps.get_model("db", "Value").objects.filter(pk__in=self.all_upstream.values("values__pk"))

    @combomethod
    def with_value(receiver, name, value_type=None, linked_to=None, search_set=None, upstream=False, only=False):
        linkable_objects = ["samples", "features", "analyses", "steps", "processes",\
                            "results", "investigations"]
        if search_set is None:
            search_set = receiver._meta.model.objects.all()
        search_set = search_set.prefetch_related("values")
        if receiver.has_upstream & upstream:
            search_set = search_set.prefetch_related("all_upstream")
            upstream_set = receiver._meta.model.objects.filter(pk__in=search_set.values("all_upstream__pk").distinct())
            search_set = search_set.union(upstream_set).distinct()
        kwargs = {"values__name": name, "pk__in": search_set}
        if value_type is not None:
            kwargs["values__type"] = value_type
        #For some reason whittling down the search_set QuerySet doesn't work
        # So we have to go to the whole table
        if linked_to is not None:
            if isinstance(linked_to, list):
                for link in linked_to:
                    kwargs["values__" + link + "__isnull"] = False
                if only:
                    for obj in linkable_objects:
                        if "values__" + obj + "__isnull" not in kwargs:
                            kwargs["values__" + obj + "__isnull"] = True
            else:
                 kwargs = {"values__" + linked_to + "__isnull": False}
                 if only:
                     for obj in linkable_objects:
                         if obj != linked_to:
                             kwargs["values__" + obj + "__isnull"] = True
        hits = receiver._meta.model.objects.all()
        hits = hits.filter(**kwargs).distinct()
        if not hits.exists():
            return False
        else:
            return hits

    # In a combomethod, obj is either the class, or an instance
    @combomethod
    def with_metadata(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_value(name, "metadata", linked_to,
                                    search_set, upstream, only)

    @combomethod
    def with_measure(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_value(name, "measure", linked_to,
                                    search_set, upstream, only)

    @combomethod
    def with_parameter(receiver, name, linked_to=None, search_set=None, upstream=False, only=False):
        if (search_set is None) and (receiver.search_set is not None):
            # Go to instance default
            search_set = receiver.search_set
        return receiver.with_value(name, "parameter", linked_to,
                                    search_set, upstream, only)

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

    # Creates bare minimum objects from the given data set
    @classmethod
    def initialize(cls, data, log=None):
        #data is a dict with {"field_name": [field data],}
        _id_fields = id_fields()
        req_fields = [ x for x in required_fields() if x.startswith(cls.base_name + "_") ]
        ref_fields = [ x for x in reference_fields() if x[0].startswith(cls.base_name + "_") ]
        single_ref_fields = [ x[0] for x in single_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        many_ref_fields = [ x for x in many_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        ref_proxies = reference_proxies()
        cls_proxies = [x for x in ref_proxies if ref_proxies[x][0].startswith(cls.base_name)]
        ids = []
        cls_proxy = False
        if (cls.base_name + "_id" not in data) and \
           (cls.base_name + "_" + cls.id_field not in data):
                cls_proxy_fields = []
                for proxy_field in cls_proxies:
                    if proxy_field in data:
                        cls_proxy = True
                        cls_proxy_fields.append(proxy_field)
                if not cls_proxy:
                    #Nothing to do for this class, so bail
                    return
       # Fast non-database data validation:
        required_proxies = dict()
        for field_name in req_fields:
            if (field_name not in data) and (field_name in ref_proxies):
                #Search for a proxy field
                proxy = False
                for proxy_field in ref_proxies[field_name]:
                    if proxy_field in data:
                        proxy = True
                        required_proxies[field_name] = proxy_field
                # If no proxy is present, raise error
                if not proxy:
                    raise ValueError("initialize %s: Missing required field name %s for object %s and no proxies found" % (cls.base_name, field_name, cls.base_name))
            elif field_name not in data:
                    raise ValueError("initialize %s: Missing required field name %s for object %s" % (cls.base_name, field_name, cls.base_name))
            if (field_name in [x[0] for x in single_ref_fields]):
                if len(data[field_name]) > 1:
                    raise ValueError("initialize %s: Can only have one item in list for atomic field %s" % (cls.base_name, field_name,))
        assert (cls.base_name + "_id" in data) or (cls.base_name + "_" + cls.id_field in data) or (cls_proxy)
        if cls.base_name + "_id" in data:
            ids.extend(data[cls.base_name + "_id"])
        if cls.base_name + "_" + cls.id_field in data:
            ids.extend(data[cls.base_name + "_" + cls.id_field])
        if cls_proxy:
            for cls_proxy_field in cls_proxy_fields:
                ids.extend(data[cls_proxy_field])
        #This should be the only true database hit for each call of this, unless references have to be pulled
        cls_queryset = cls.get_queryset(data)
        found_ids = [str(x) for x in cls_queryset.values_list(cls.id_field, flat=True)]
        # If the id field is found in data, iterate over the ids
        ref_objects = defaultdict(dict)
        object_list = Object.get_object_classes()
        for _id in ids:
            # Check if the id exists in the database, according to our previous query
            if isinstance(_id, int):
                # Nothing to do for an initialize
                continue
            _id = str(_id)
            if not _id in found_ids:
                #Create the new one
                kwargs = {cls.id_field: _id}
                for field in req_fields:
                    django_field = field.split("_")[1]
                    if field in single_ref_fields:
                        if field in required_proxies:
                            ref_id = data[required_proxies[field]][0]
                        else:
                            ref_id = data[field][0]
                        # Grab it as a query
                        ref_model = [x[2] for x in ref_fields if x[0]==field][0]
                        #Only grab Objects
                        if hasattr(ref_model, "base_name"):
                            if (ref_id in ref_objects[ref_model.base_name]):
                                obj = ref_objects[ref_model.base_name][ref_id]
                            else:
                                if isinstance(ref_id, int):
                                    ref_id_field = "id"
                                else:
                                    ref_id_field = ref_model.id_field
                                try:
                                    obj = ref_model.objects.get(**{ref_id_field: ref_id})
                                    ref_objects[ref_model.base_name][ref_id] = obj
                                except:
                                    raise ValueError("initialize %s: Cannot find referenced required %s '%s'" % (cls.base_name, ref_model.base_name, ref_id))
                            kwargs[django_field] = obj
                    elif django_field != cls.id_field:
                        kwargs[django_field] = data[field][0]
                new_obj = cls()
                for field in kwargs:
                    setattr(new_obj, field, kwargs[field])
                new_obj.save()

    @classmethod
    def update(cls, data, log=None):
        _id_fields = id_fields()
        _all_fields = [ x for x in all_fields() if x.startswith(cls.base_name + "_") ]
        ref_fields = [ x for x in reference_fields() if x[0].startswith(cls.base_name + "_") ]
        single_ref_fields = [ x for x in single_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        many_ref_fields = [ x for x in many_reference_fields() if x[0].startswith(cls.base_name + "_") ]
        ref_proxies = reference_proxies()
        # data validation
        for field_name in [x for x in _all_fields if x in data]:
            if (field_name in single_ref_fields):
                if len(data[field_name]) > 1:
                    raise ValueError("update: Can only have one item in list for atomic field %s" % (field_name,))
        #This is all the objects that already exist
        cls_queryset = cls.get_queryset(data)
        # If the id field is found in data, iterate over the ids
        obj_id_in_data = [ x for x in _id_fields if x.startswith(cls.base_name) and (x in data)]
        object_list = Object.get_object_classes()
        for id_field in obj_id_in_data:
            for _id in data[id_field]:
                # Check if the id exists in the database, according to our previous query
                obj_queryset = cls_queryset.filter(**{id_field.split("_")[1]: _id})
                if not obj_queryset.exists():
                    raise ValueError("update: %s %s not found when attempting to update. Did you use initialize?" % (cls.base_name,_id))
                else:
                    obj = obj_queryset.get()
                    for field in [x for x in _all_fields if (x not in _id_fields) and (x.startswith(cls.base_name))]:
                        proxy_fields = []
                        if (field not in data) and (field in ref_proxies) and (not field.endswith("_upstream")):
                            for proxy in ref_proxies[field]:
                                if proxy in data:
                                    proxy_fields.append(proxy)
                            if (field in required_fields()) and (len(proxy_fields) == 0):
                                raise ValueError("Field %s required and not found, and no proxy ID fields found." % (field,))
                        db_datum = getattr(obj, field.replace(cls.base_name+"_",""))
                        #Blank, feel free to overwrite
                        if (field not in [x[0] for x in ref_fields]) and (field in data):
                            # If it isn't a reference, we just set the data
                            if (db_datum == "") or (db_datum == None):
                                setattr(obj, field.replace(cls.base_name+"_",""), data[field][0])
                            #elif datum != data[field][0]:
                            #    #TODO: set this as a warning? Overwrite?
                            #    pass
                        elif (field in [x[0] for x in ref_fields]):
                            # If it is a reference, we need to fetch it, then set it
                            # We also need to translate reverse fields into their ID fields
                            ref_model = [x[2] for x in ref_fields if x[0]==field][0]
                            if hasattr(ref_model, "base_name"):
                                proxy_fields.append(field)
                                for search_field in proxy_fields:
                                    if search_field in data:
                                        for ref_id in data[search_field]:
                                            if isinstance(ref_id, int):
                                                ref_id_field = "id"
                                            else:
                                                ref_id_field = ref_model.id_field
                                            try:
                                                ref_obj = ref_model.objects.get(**{ref_id_field: ref_id})
                                            except:
                                                #TODO: Set this to a warning?
                                                raise ValueError("update: Cannot find referenced %s '%s'" % (ref_model.base_name, ref_id))
                                            if field in [x[0] for x in many_ref_fields]:
                                                getattr(obj, field.replace(cls.base_name+"_","")).add(ref_obj)
                                                if field == cls.base_name + "_upstream":
                                                    # In order to update the symmetrical
                                                    # all_upstream/all_downstream fields
                                                    # we add ref_obj to upstream and all_upstream
                                                    # then we add all of ref_obj's upstream to
                                                    # obj, and all of obj's downstream to
                                                    # ref_obj's downstream
                                                    # and then we have to update the cross
                                                    # references of all other steps to one
                                                    # another, saving as we let variables go
                                                    obj.all_upstream.add(ref_obj)
                                                    upstream_qs = ref_obj.all_upstream.all()
                                                    downstream_qs = obj.all_downstream.all()
                                                    obj.all_upstream.add(*upstream_qs)
                                                    ref_obj.all_downstream.add(*downstream_qs)
                                                    ref_obj.save()
                                                    for down_obj in downstream_qs:
                                                        for up_obj in upstream_qs:
                                                            down_obj.all_upstream.add(up_obj)
                                                        down_obj.save()
                                            else:
                                                if (db_datum == "") or (db_datum == None):
                                                    setattr(obj, field.replace(cls.base_name+"_",""), ref_obj)
                                                    #TODO: Set else to a warning? Overwrite?
                                #elif datum != data[field]:
                            #    pass
                                #TODO: Add a warning that it didn't overwrite
                    obj.save()

    def get_node_attrs(self, values=True):
        htm = "<<table border=\"0\"><tr><td colspan=\"3\"><b>%s</b></td></tr>" % (self.base_name.upper(),)
        if not values:
           sep = ""
        else:
           sep = "border=\"1\" sides=\"b\""
        htm += "<tr><td colspan=\"3\" %s><b><font point-size=\"18\">%s</font></b></td></tr>" % (sep, str(getattr(self, self.id_field)))
        if values:
            val_names = list(self.values.all().values_list("name","type").distinct())
            val_counts = []
            for name, type in val_names:
                count = self.values.filter(name=name, type=type).count()
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
        return attrs

    def get_node(self, values=True):
        dot = gv.Digraph("node graph", format='svg')
        dot.attr(size="5,5!")
        dot.node(**self.get_node_attrs(values=values))
        return dot

    def get_stream_graph(self, values=False):
        dot = gv.Digraph("stream graph", format='svg')
        dot.attr(size="12,12!")
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
        return dot

    @classmethod
    def get_object_classes(cls):
        return cls.__subclasses__()

def all_fields():
    object_list = Object.get_object_classes()
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if (x.name not in ["search_vector", "content_type", \
                     "all_upstream", "object_id", "category_of"]) and \
                     x.concrete] for Obj in object_list] for item in sublist]

def id_fields():
    object_list = Object.get_object_classes()
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if (x.name in ["id", "name", "uuid"]) and (x.concrete)] \
                         for Obj in object_list] for item in sublist]

def required_fields():
    object_list = Object.get_object_classes()
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if x.name not in ["search_vector", "content_type", \
                                    "object_id", "category_of"] and x.concrete \
                     and hasattr(x,"blank") and not x.blank] \
                         for Obj in object_list] for item in sublist]

def reference_fields():
    object_list = Object.get_object_classes()
    # Returns tuples of the field name, from model, and to model
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, \
                                                      x.model, \
                                                      x.related_model) \
                 for x in Obj._meta.get_fields() if \
                 (x.name not in ["values", "categories", "all_upstream", \
                 "content_type", "object_id", "category_of"]) and x.concrete \
                 and x.is_relation] for Obj in object_list] for item in sublist]

def single_reference_fields():
    object_list = Object.get_object_classes()
    # Returns tuples of the field name, from model, and to model
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, \
                                                      x.model, \
                                                      x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream", "content_type", \
                 "object_id", "category_of"] and x.concrete and x.many_to_one] \
                 for Obj in object_list] for item in sublist]


def many_reference_fields():
    object_list = Object.get_object_classes()
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, x.model, x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream"] \
                 and x.concrete and (x.many_to_many or x.one_to_many)] for Obj in object_list] \
                 for item in sublist]

def reference_proxies():
    object_list = Object.get_object_classes()
    proxies = defaultdict(list)
    for field, source_model, ref_model in reference_fields():
        if (ref_model.base_name not in ["value", "category", "file"]):
            for proxy in ref_model.get_id_fields():
                proxies[field].append(proxy)
    return proxies


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

