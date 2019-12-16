from collections import defaultdict, OrderedDict
import itertools

from django.db import models, transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import polymorphic
from polymorphic.models import PolymorphicModel
from combomethod import combomethod

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector

import pandas as pd
import numpy as np
import arrow
import uuid

from .data_types import Data, DataSignature
from .object import Object
from .step import Step
from .result import Result
from .analysis import Analysis
from .process import Process

from django_pandas.managers import DataFrameQuerySet

class Value(PolymorphicModel):
    base_name = "value"
    plural_name = "values"

    # `description` collides with a reverse accessor whose name can't be changed easily through django-polymorphic
    str_description = "All-purpose value/metadata class. Can be attached to anything for any reason. For clarity, use a more specific type if one is appropriate."

    search_vector = SearchVectorField(null=True)

    linkable_objects = ["steps", "processes", "investigations", "analyses", "results", "samples", "features"]
    required_objects = []

    def __str__(self):
        return "(" + self.base_name.capitalize() + ") " + self.signature.get().name + ": " + str(self.data.get())

    @combomethod
    def info(receiver):
        out_str = "Value type name: %s\n" % (receiver.base_name.capitalize(),)
        out_str += receiver.str_description + "\n"
        if type(receiver) == polymorphic.base.PolymorphicModelBase:
            out_str += "There are %d %s in this QUOR'em instance\n" % (receiver.objects.count(), receiver.plural_name)
            out_str += "%s can be linked to %s\n" % (receiver.plural_name.capitalize(), ", ".join(receiver.linkable_objects))
            if receiver.required_objects:
                out_str += "%s must contain a link to %s\n" % (receiver.plural_name.capitalize(), ", ".join(receiver.required_objects))
        else:
            object_counts = {}
            for Obj in Object.get_object_types():
                object_counts[Obj.plural_name] = getattr(receiver, Obj.plural_name).count()
            out_str += "Linked to %s Objects (%s)\n" % (sum(list(object_counts.values())), ", ".join(["%d %s" % (y,x) for x,y in object_counts.items()]))
        return out_str

    def qs(self):
        return self._meta.model.objects.filter(pk=self.pk)

    @classmethod
    def get_or_create(cls, name, data, signature=None, **kwargs):
        kwargs["value_type"] = cls._clean_value_type(**kwargs)
        if kwargs["value_type"] != Matrix:
            vals = kwargs["value_type"].get(name=name, all_types=False, signature=signature, **kwargs)
        else:
            vals = Matrix.objects.none() #NOTE: I think skipping the get for Matrices saves a lot of time...
        if not vals.exists():
            val = kwargs["value_type"].create(name, data, signature=signature, **kwargs)
            return kwargs["value_type"].objects.filter(pk=val.pk)
        else:
            return vals

    @classmethod
    def column_headings(cls):
        return [("value_type", True),
                ("value_object", True),
                ("value_name", True),
                ("value_data", True),
                ("data_type", False)] + \
               [("n_" + Obj.plural_name, False) for Obj in Object.get_object_types()]

    @classmethod
    def _parse_kwargs(cls, **kwargs):
        # Generic function to pull in kwargs and make the necessary adjustments
        # and checks to standardize the input
        newkwargs = {}
        fetch_signature = False #Only grab this if we need to be explicit about it
        signatureargs = {}
        for Obj in Object.get_object_types():
            if ("n_" + Obj.plural_name in kwargs) and (Obj.plural_name in kwargs):
                fetch_signature = True
            if ("n_" + Obj.plural_name in kwargs):
                signatureargs[Obj.plural_name] = int(kwargs["n_" + Obj.plural_name])
                del kwargs["n_" + Obj.plural_name]
            if (Obj.plural_name in kwargs):
                if Obj.plural_name not in signatureargs:
                    if type(kwargs[Obj.plural_name]) == models.query.QuerySet:
                        signatureargs[Obj.plural_name] = kwargs[Obj.plural_name].count()
                    elif type(kwargs[Obj.plural_name]) == bool:
                        if kwargs[Obj.plural_name]:
                            signatureargs[Obj.plural_name] = -2 #-2 Means any positive value
                        else:
                            signatureargs[Obj.plural_name] = 0
        newkwargs["value_type"] = cls._clean_value_type(**kwargs)
        if "value_name" in kwargs:
            newkwargs["name"] = kwargs["value_name"]
        if "value_data" in kwargs:
            newkwargs["data"] = kwargs["value_data"]
        if "data_type" in kwargs:
            newkwargs["data_type"] = kwargs["data_type"]
        vobj_keys = [x for x in kwargs if x.startswith("value_object")]
        for vobj_key in vobj_keys:
            vobj = Object.get_object_types(type_name=kwargs[vobj_key])
            if (vobj.plural_name in kwargs) and (type(kwargs[vobj.plural_name]) in [models.query.QuerySet, DataFrameQuerySet]):
                continue # We already have it in QS format
            qsdata = defaultdict(list)
            for arg in kwargs:
                if arg.split(".")[0] == vobj.base_name+"_"+vobj.id_field:
                    qsdata[arg.split(".")[0]].append(kwargs[arg])
            vobjs = vobj.get_queryset(qsdata)
            newkwargs[vobj.plural_name] = vobjs
        if fetch_signature:
            signature = DataSignature.get(name=newkwargs["name"], value_type=newkwargs["value_type"], **signatureargs)
            newkwargs["signature"] = signature
        return newkwargs

    @classmethod
    def get_value_types(cls, name=None, data=None, type_name=None, data_types=False, **kwargs):
        if (name is None) and (type_name) is None:
            return cls.__subclasses__() + [Value]
        elif type_name is not None:
            if type_name.lower() == "value":
                return Value
            for val in Value.get_value_types():
                if (val.base_name == type_name.lower()) or (val.plural_name == type_name.lower()):
                    return val
        object_counts = {}
        for Obj in Object.get_object_types():
            if Obj.plural_name in kwargs:
                objs = kwargs[Obj.plural_name]
                if type(objs) == int:
                    object_counts[Obj.plural_name] = objs
                elif type(objs) == models.query.QuerySet:
                    object_counts[Obj.plural_name] = objs.count()
            else:
                object_counts[Obj.plural_name] = 0
        signatures = DataSignature.objects.filter(name=name, value_type=ContentType.objects.get_for_model(cls), object_counts=object_counts)
        if data_types:
            return signatures.values("value_type", "data_types")
        else:
            return signatures.values("value_type")

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector= (SearchVector('name', weight='A')))

    @classmethod
    def _clean_value_type(cls, **kwargs):
        if "value_type" not in kwargs:
            return cls
        value_type = kwargs["value_type"]
        if type(value_type) == str:
            if value_type.lower() == "value":
                return Value
            return Value.get_value_types(type_name=value_type)
        if type(value_type) == polymorphic.base.PolymorphicModelBase:
            return value_type
        if type(value_type) == ContentType:
            return value_type.class_model()
        return cls

    @classmethod
    def create(cls, name, data, signature=None, **kwargs):
        for obj in cls.required_objects:
            t = Object.get_object_types(type_name=obj)
            if (t.base_name not in kwargs) and (t.plural_name not in kwargs):
                raise ValueError("Missing required links to %s for value %s" % (obj, name))
        for Obj in Object.get_object_types():
            if Obj.plural_name in kwargs:
                if type(kwargs[Obj.plural_name]) not in  [models.query.QuerySet, DataFrameQuerySet]:
                    raise ValueError("Object arguments to Value.create() methods must be QuerySets, or left out of the arguments")
        linked_objects = [Obj.plural_name for Obj in Object.get_object_types() if Obj.plural_name in kwargs]
        for obj in linked_objects:
            if obj not in cls.linkable_objects:
                raise ValueError("Cannot link %s to Values of type %s" % (obj, cls.__name__))
        kwargs["value_type"] = cls._clean_value_type(**kwargs)
        signatures = DataSignature.get_or_create(name=name, **kwargs)
        add_dtype_to_signature = False
        if len(signatures) == 1:
            #If unique, use that one
            signature = signatures[0]
        else:
            #Ambiguous: need clarification in the form of a n_<objects> kwargs specifying the positive number, -1, or -2
            raise ValueError("Multiple DataSignatures found. Provide n_<objects> arguments in kwargs to resolve the ambiguity, or provide the signature explicitly")
        if 'data_type' in kwargs:
            data_type = kwargs['data_type']
            if data_type == "auto":
                data_type = Data.infer_type(data)
            else:
                data_type = Data.get_data_types(type_name=data_type)
            add_dtype_to_signature = True
        elif signature.data_types.exists():
            data_type = signature.data_types.first().model_class() #TODO; Allow users to select a preferred default
        else:
            data_type = Data.infer_type(data)
            add_dtype_to_signature = True
        data = data_type.get_or_create(data)
        value = kwargs["value_type"]()
        value.save()
        signature.values.add(value)
        data.values.add(value)
        if add_dtype_to_signature:
            ct = ContentType.objects.get_for_model(data_type)
            signature.data_types.add(ct)
        for Obj in Object.get_object_types():
            if Obj.plural_name in kwargs:
                for obj in kwargs[Obj.plural_name]:
                    obj.values.add(value)
        return value

    def get_links(self, return_querysets=False):
        #Since this is the back side of these relationships, this should be quickest?
        linked_objects = []
        object_querysets = []
        for Obj in Object.get_object_types():
            qs = Obj.objects.filter(values=self.pk)
            if qs:
                linked_objects.append(Obj)
                if return_querysets:
                    object_querysets.append(qs)
        if return_querysets:
            return dict(zip(linked_objects, object_querysets))
        else:
            return linked_objects

    @classmethod
    def get(cls, name, signature=None, **kwargs):
        # kwargs should have as keys the plural_name attribute of Objects
        # It can contain either:
        #  - A QuerySet of those objects
        #  - A boolean value
        #  - An integer
        # If a QuerySet, it MUST be linked to those and only those
        # If a boolean value, it is either linked (1) or not (0)
        # If an integer, it is linked to that many of those objects
        # If count_querysets, it will return anything with the same
        # number of Objects as each of the querysets
        # Return the Value/subclass with this name and links
        object_querysets = {}
        for Obj in Object.get_object_types():
            if (Obj.plural_name in kwargs):
                object_querysets[Obj.plural_name+"__in"] = kwargs[Obj.plural_name]
        kwargs["value_type"] = cls._clean_value_type(**kwargs)
        if signature is None:
            signatures = DataSignature.get(name=name, **kwargs)
            if not signatures.exists():
                return kwargs["value_type"].objects.none()
            elif signatures.count() > 1:
                raise ValueError("Multiple Signatures possible for this input. Specify the number of Objects explicitly with a 'n_object' kwarg")
        return kwargs["value_type"].objects.filter(pk__in=signatures.values("values"), **object_querysets)

class Parameter(Value):
    base_name = "parameter"
    plural_name = "parameters"

    str_description = "A Parameter must be tied to a Step, and represents an independent variable involved in the Step"

    linkable_objects = ["steps", "processes", "analyses", "results"]
    required_objects = ["steps"]
    # This is the order in which Parameters are prioritized
    object_precedence = [(Step, Result), (Step, Analysis), (Step, Process), (Step,)]

    @classmethod
    def get(cls, name, signature=None, **kwargs):
        # Find the level being requested
        # Check what we can infer
        if "steps" not in kwargs:
            if "results" in kwargs:
                result = kwargs["results"].first() # Should only be one
                step = result.source_step
            else:
                raise ValueError("Parameters must be requested relative to a Step")
        else:
            steps = kwargs["steps"]
            assert steps.count() == 1, "Only one Step can be linked to a Parameter"
            step = steps.first()
        parameters = step.values.instance_of(cls).filter(signature__name=name)
        object_list = ["results", "analyses", "processes"]
        assert sum([x in kwargs for x in object_list]) <= 1, "Only one of 'results', 'analyses', or 'processes' allowed in Parameter.get()"
        for objs in object_list:
            if (objs in kwargs) and kwargs[objs].exists():
                parameters = parameters.filter(**{objs+"__in": kwargs[objs]})
            else:
                parameters = parameters.filter(**{objs+"__isnull": True})
        return parameters

    @classmethod
    def get_or_create(cls, name, data, **kwargs):
        assert "steps" in kwargs, "'steps' keyword must be provided to get a Parameter"
        assert kwargs["steps"].count() == 1, "Parameter must only link to one Step"
        steps = kwargs["steps"]
        step = steps.get()
        # Get the highest precedence object in kwargs
        for obj in ["results", "analyses", "processes", "steps"]:
            if obj in kwargs:
                top_obj = kwargs[obj].get()
                if obj in ["analyses", "processes"]:
                    parameters = top_obj.get_parameters(steps=steps)
                else:
                    parameters = top_obj.get_parameters()
                break
        # Create a new one
        if name not in parameters[step.pk]:
            val = cls.create(name, data, **kwargs)
            return val.qs()
        else: #Check if the data matches, and if not, make a new one at the proper level
            db_param = parameters[step.pk][name][0]
            db_value = db_param.data.get().get_value()
            in_value = data
            if db_value == in_value:
                return db_param.qs()
            if str(db_value) == str(in_value):
                return db_param.qs()
            # Coerce using each of the data types available for this signature and check if that matches
            for data_type in db_param.signature.get().data_types.all():
                cast_fn = data_type.model_class().cast_function
                casted_value = cast_fn(in_value)
                casted_db_value = cast_fn(db_value)
                if db_value == casted_value:
                    return db_param.qs()
                if casted_db_value == casted_value:
                    return db_param.qs()
                if str(db_value) == str(casted_value):
                    return db_param.qs()
                if str(casted_db_value) == str(casted_value):
                    return db_param.qs()
            # Didn't match any of our standard ways to compare, so let's make a new one
            val = cls.create(name, data, **kwargs)
            return val.qs()

    def is_default(self, obj):
        return not obj.values.prefetch_related("signature__name").filter(signature__name=self.name).exists()

    def is_override(self, obj):
        return not self.is_default(obj)

class Measure(Value):
    base_name = "measure"
    plural_name = "measures"

    str_description = "A Measure represents a measurement or a computation that is obtained through a Result"

    required_objects = ["result"]

class File(Value):
    base_name = "file"
    plural_name = "files"

    str_description = "A value for keeping track of Files that are either on the QUOR'em server or elsewhere"

class Category(Value):
    # Links to a homogeneous set of Objects, providing potentially-overlapping categories
    #TODO: Properly enforce homogeneity
    base_name = "category"
    plural_name = "categories"

    str_description = "A Category is a quick descriptor or tag for an object"

class State(Value):
    # Keeps track of the state of a given object. This can be employed for lots of different uses.
    # Wet-lab: keep track of whether a sample is processed/sequenced
    # Computational: keep track of whether an analysis/computation has been run on a Result, Sample etc.
    base_name = "state"
    plural_name = "states"

    str_description = "A State is an indicator of some milestone for an object"

class Description(Value):
    # Stores the various descriptions possible about a given linked item or items
    # Having Description here allows for "multi-object" descriptions that baked-in
    # fields won't allow
    base_name = "description"
    plural_name = "descriptions"

    str_description = "A Description is a text description of the object"
    #TODO: Properly enforce text-only data

class Date(Value):
    # Stores all the important dates for an object, including system ones like "created_on", "last_updated", etc.
    base_name = "date"
    plural_name = "dates"

    str_description = "A Date that is significant for the object. Default date format is 'DD/MM/YYYY'"
    #TODO: Enforce

class Location(Value):
    # Stores all the important locations for an object
    # Can be a geographical location, web URL, local filepath, etc.
    base_name = "location"
    plural_name = "locations"

    str_description = "A Location describes where an object is. This can be GPS coordinates, a simple text description, or a web link."

class Version(Value):
    # Stores all versions for an object
    # Can store protocol version, software version, draft version, etc.
    base_name = "version"
    plural_name = "versions"

    str_description = "Version values store version information for software, protocols, revisions, etc. See the VersionDatum type."

class Reference(Value):
    # Stores References for an Object (i.e., citations)
    # Can be Bibtex, or text, or a local/external link
    base_name = "reference"
    plural_name = "references"

    str_description = "Reference values point at something, such as an academic work (Bibtex reference, text reference), or a web link"

class WikiLink(Value):
    # Stores links that are specifically to the Wiki, especially automated reports
    base_name = "wikilink"
    plural_name = "wikilinks"

    str_description = "A Value specifically for links to the internal QUOR'em Wiki"

class Image(Value):
    # Stores images. Useful for pictures of plates, wells, tubes, data etc.
    base_name = "image"
    plural_name = "images"

    str_description = "Image values point at Images on the server or on the web"

class Role(Value):
    # Stores User roles for each object
    # e.g., owner, technician, administrator, or whatever the team requires
    base_name = "role"
    plural_name = "roles"

    str_description = "A Role describes which Users have responsibilities for a set of Objects"

    required_objects = ["user"]

class Permission(Value):
    # Stores access permissions for users and objects
    # We can use this to whitelist/blacklist, add individual or group permissions
    # things like "can_write", "can_read", "can_export" can go here
    base_name = "permission"
    plural_name = "permissions"

    str_description = "A Permission for linked Users that apply to linked Objects"

    required_objects = ["user"]

class Group(Value):
    # Stores groups of users so permissions can be set en masse,
    # and maybe groups of other things?
    base_name = "group"
    plural_name = "groups"

    str_description = "Groups represent a grouping of Objects, that isn't necessarily non-overlapping"

class Matrix(Value):
    # A special datatype that stores sparse matrices for all objects linked to it
    # Matrices must be stored sparsely, and indexes must be object pks for absolute consistency
    base_name = "matrix"
    plural_name = "matrices"

    str_description = "A two-dimensional, typically numeric, data structure such as a feature-by-sample matrix, a distance matrix, etc."

class Partition(Value):
    # A datatype that stores a bitstring bloomfilter that defines a complete partition of
    # all objects linked to it (that is, for all pairwise combinations of
    # Objects O linked to Partition P, each object has exactly one label)
    # This is critical Ananke integration groundwork
    base_name = "partition"
    plural_name = "partitions"

    str_description = "A Partition is a grouping where every Object in the set has exactly one label"
