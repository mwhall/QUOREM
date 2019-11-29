from collections import defaultdict
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

object_classes = Object.get_object_classes()

class Value(PolymorphicModel):
    base_name = "value"
    plural_name = "values"

    # `description` collides with a reverse accessor whose name can't be changed easily through django-polymorphic 
    str_description = "All-purpose value/metadata class. Can be attached to anything for any reason. For clarity, use a more specific type if one is appropriate."

    name = models.CharField(max_length=512)
    data = models.ForeignKey('Data', related_query_name = "values", on_delete=models.CASCADE)
    signature = models.ForeignKey('DataSignature', related_name = 'values', on_delete=models.CASCADE)

    search_vector = SearchVectorField(null=True)

    linkable_objects = [Obj.plural_name for Obj in object_classes]
    required_objects = []

    def __str__(self):
        return self.name

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
            for Obj in object_classes:
                object_counts[Obj.plural_name] = getattr(receiver, Obj.plural_name).count()
            out_str += "Linked to %s Objects (%s)\n" % (sum(list(object_counts.values())), ", ".join(["%d %s" % (y,x) for x,y in object_counts.items()]))
        return out_str

    @classmethod
    def get_or_create(cls, name, data, **kwargs):
        vals = cls.get(name=name, all_types=False, **kwargs)
        if not vals.exists():
            val = cls.create(name, data, **kwargs)
            return val
        else:
            return vals

    @classmethod
    def column_headings(cls):
        return ["value_type", "target_objects", "value_name", "value"] + [Obj.plural_name for Obj in object_classes]

    @classmethod
    def get_value_types(cls, name=None, data=None, type_name=None, data_types=False, **kwargs):
        if name is None:
            return cls.__subclasses__()
        if type_name is not None:
            for val in Value.get_value_types():
                if (val.base_name == type_name.lower()) or (val.plural_name == type_name.lower()):
                    return val
        object_counts = {}
        for Obj in object_classes:
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
            return Contentsignatures.values("value_type", "data_types")
        else:
            return signatures.values("value_type")

    @classmethod
    def update_search_vector(cls):
        cls.objects.update(
            search_vector= (SearchVector('name', weight='A')))

    @classmethod
    def create(cls, name, data, signature=None, **kwargs):
        for obj in cls.required_objects:
            if obj not in kwargs:
                raise ValueError("Missing required links to %s for value %s" % (obj, name))
        for Obj in object_classes:
            if Obj.plural_name in kwargs:
                if type(kwargs[Obj.plural_name]) != models.query.QuerySet:
                    raise ValueError("Object arguments to Value.create() methods must be QuerySets, or left out of the arguments")
        kwargs['value_type'] = cls
        linked_objects = [Obj.plural_name for Obj in object_classes if Obj.plural_name in kwargs]
        for obj in linked_objects:
            if obj not in cls.linkable_objects:
                raise ValueError("Cannot link %s to Values of type %s" % (obj, cls.__name__))
        signatures = DataSignature.get_or_create(name=name, **kwargs)
        if len(signatures) == 1:
            #If unique, use that one
            signature = signatures[0]
        else:
            #Ambiguous: need clarification in the form of a n_<objects> kwargs specifying the positive number, -1, or -2
            raise ValueError("Multiple DataSignatures found. Provide n_<objects> arguments in kwargs to resolve the ambiguity, or provide the signature explicitly")
        if 'data_type' in kwargs:
            data_type = kwargs['data_type']
            ct = ContentType.objects.get_for_model(data_type)
            signature.data_types.add(ct)
        elif signature.data_types.exists():
            data_type = signature.data_types.first().model_class() #TODO; Allow users to select a preferred default
        else:
            data_type = Data.infer_type(data)
            signature.data_types.add(ContentType.objects.get_for_model(data_type))
        data = data_type.get_or_create(data)
        value = cls(name = name, data = data, signature = signature)
        value.save()
        for Obj in object_classes:
            if Obj.plural_name in kwargs:
                for obj in kwargs[Obj.plural_name]:
                    obj.values.add(value)
        return value
    
    def get_links(self, return_objects=False):
        #Since this is the back side of these relationships, this should be quickest?
        linked_objects = []
        object_querysets = []
        for Obj in object_classes:
            qs = Obj.objects.filter(values=self.pk)
            if qs:
                linked_objects.append(Obj.plural_name)
                if return_objects:
                    object_querysets.append(qs)
        if return_objects:
            return dict(zip(linked_objects, object_querysets))
        else:
            return linked_objects

    @classmethod
    def get(cls, name, **kwargs):
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
        for Obj in object_classes:
            if (Obj.plural_name in kwargs) and (type(kwargs[Obj.plural_name])==models.query.QuerySet):
                object_querysets[Obj.plural_name + "__in"] = kwargs[Obj.plural_name]
        kwargs['value_type'] = cls
        signatures = DataSignature.get(name=name, **kwargs)
        if signatures.count() == 1:
            return signatures.get().values.filter(**object_querysets)
        return cls.objects.filter(pk__in=signatures.select_related("values").values("values")).filter(**object_querysets)

class Parameter(Value):
    base_name = "parameter"
    plural_name = "parameters"

    str_description = "A Parameter must be tied to a Step, and represents an independent variable involved in the Step"

    linkable_objects = ["steps", "processes", "analyses", "results"]
    required_objects = ["steps"]

class Measure(Value):
    base_name = "measure"
    plural_name = "measures"

    str_description = "A Measure represents a measurement or a computation that is obtained through a Result"

    required_objects = ["result"]

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
