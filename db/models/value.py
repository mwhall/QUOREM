from collections import defaultdict
import itertools

from django.db import models, transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector

import pandas as pd
import numpy as np
import arrow
import uuid

class Value(models.Model):
    base_name = "value"
    plural_name = "values"

    default_date_format = "DD/MM/YYYY"

    PARAMETER = 'parameter'
    METADATA = 'metadata'
    MEASURE = 'measure'
    VALUE_TYPES = (
            (PARAMETER, 'Parameter'),
            (METADATA, 'Metadata'),
            (MEASURE, 'Measure'))
    name = models.CharField(max_length=512)
    type = models.CharField(max_length=9, choices=VALUE_TYPES)
    # This generic relation links to a polymorphic Val class
    # Allowing Value to be str, int, float, datetime, etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    linkable_objects = ["samples", "features", "analyses", "steps", \
                        "processes", "results", "investigations"]

    search_vector = SearchVectorField(null=True)

    def __str__(self):
        return self.name + ": " + str(self.content_object.value)

    @classmethod
    def create_value(cls, value_name, value_type, value, linked_to=[], value_model=None):
        if value_model == None:
            value_model = cls.infer_type(value_name, value_type, value)
        new_val = value_model()
        try:
            new_val.value = value_model.cast_function(value)
        except Result.DoesNotExist:
            print("Warning, could not find Result %s, abandoning adding %s %s" % (str(value), value_type, value_name))
            return
        new_val.save()
        new_Value = Value()
        new_Value.name = value_name
        new_Value.type = value_type
        new_Value.content_object = new_val
        new_Value.save()
        for qs in linked_to:
            if qs.exists():
                getattr(new_Value, qs.model.plural_name).add(*qs)

    @classmethod
    def _table_value_targets(cls, table, unique=False):
            value_target_combinations = list(table[[x for x in table.columns if x.startswith("value_target")]].drop_duplicates().agg(lambda x: list(x.dropna()), axis=1))
            if unique:
                unique_targets = set()
                ut_add = unique_targets.add
                for element in itertools.filterfalse(unique_targets.__contains__, [y for x in value_target_combinations for y in x]):
                    ut_add(element)
                unique_targets = list(unique_targets)
                return unique_targets
            return value_target_combinations

    @classmethod
    def add_parameters(cls, table, database_table, log=None):
        print("Adding parameters")
        # PARAMETERS
        # Heuristics:
        # - All Parameters must be linked to a Step, as all parameters are relative to a Step
        # - If it is an Analysis or Process being linked, we speed it up by specifying steps=[source_step]
        # - Sort measures by Step
        # - Start with things linked only to the Step, then Step+Process, Step+Analysis, Step+Result, inserting new Values only when needed

        #Now that we've aggregated all the parameter data, we want to go top-down so we don't miss any Values in the lower objects
        unique_targets = cls._table_value_targets(table, unique=True)
        # Use this dict to track all of the levels of input parameters
        parameter_data = {"process": {"analysis": {"result": {"parameters" : defaultdict(lambda: defaultdict(dict))},
                                                     "parameters": defaultdict(lambda: defaultdict(dict))},
                                        "parameters": defaultdict(lambda: defaultdict(dict))},
                          "parameters": defaultdict(dict)}
        # Organize the data by step (all parameters attached to a step)
        print("Organizing data")
        for step in table["step_name"].unique():
             subtable = table[table["step_name"]==step]
             subtable = subtable[[x for x in table.columns if \
                                  (x in ["value", "value_name"]) or \
                                   x.startswith("value_target") or \
                                  (x.split("_")[0] in unique_targets) and\
                                   (x in id_fields())]].drop_duplicates()
             row_targets = cls._table_value_targets(subtable, unique=True)
             for ind, series in subtable.iterrows():
                 if len(row_targets) == 1:
                 # Only targeting a Step
                     parameter_data["parameters"][series["step_name"]][series["value_name"]] = series["value"]
                 elif "process" in row_targets:
                     parameter_data["process"]["parameters"][series["process_name"]][series["step_name"]][series["value_name"]] = series["value"]
                 elif "analysis" in row_targets:
                     parameter_data["process"]["analysis"]["parameters"][series["analysis_name"]][series["step_name"]][series["value_name"]] = series["value"]
                 elif "result" in row_targets:
                     parameter_data["process"]["analysis"]["result"]["parameters"][series["result_uuid"]][series["step_name"]][series["value_name"]] = series["value"]
        # Loop through these models, fetch the relevant objects in bulk, then fetch individually and query the parameters
        parameter_list = [ (Step, parameter_data["parameters"]),
                           (Process, parameter_data["process"]["parameters"]),
                           (Analysis, parameter_data["process"]["analysis"]["parameters"]),
                           (Result, parameter_data["process"]["analysis"]["result"]["parameters"])]
        print("Validating data")
        for model, obj_list in parameter_list:
            instances = model.objects.filter(**{model.id_field + "__in": [x for x in obj_list.keys() if x!="parameters"]}).prefetch_related("values")
            for Obj in obj_list:
                obj = instances.filter(**{model.id_field:Obj})
                db_params = obj.get().get_parameters()
                queryset_list = [obj]
                if model.base_name == "step":
                    in_params = obj_list[Obj]
                    diff_params = {x: y for x, y in in_params.items() if (x not in db_params) or ((x in db_params) and (str(db_params[x])!=str(in_params[x])))}
                    for value_name, value in diff_params.items():
                        cls.create_value(value_name, "parameter", value, linked_to=queryset_list)
                else:
                    for step in obj_list[Obj]:
                        step_obj = Step.objects.filter(name=step)
                        in_params = obj_list[Obj][step]
                        queryset_list = [obj, step_obj]
                        if model.base_name == "result":
                            step_params = db_params
                        else:
                            step_params = db_params[step]
                        diff_params = {x: y for x, y in in_params.items() if (x not in step_params) or ((x in step_params) and (str(step_params[x])!=str(in_params[x])))}
                        for value_name, value in diff_params.items():
                            cls.create_value(value_name, "parameter", value, linked_to=queryset_list)

    @classmethod
    def add_measures(cls, input_table, database_table, log=None):
        print("Adding measures")
        # MEASURES
        # Heuristics:
        # - All Measures must be linked to a Result, as a measure without a Result is metadata that has no provenance
        # Build up kwargs for all items in the table
        _id_fields = id_fields()
        result_id_fields = Result.get_id_fields()
        model_cache = {}
        with transaction.atomic():
            for idx, series in input_table.iterrows():
                series = series.dropna()
                value_name = series["value_name"]
                if sum([x in series for x in result_id_fields]) == 0:
                    if log is not None:
                        log.error("Line %d: Measure %s requires a Result", idx, value_name)
                    continue
                value = series["value"]
                targets = [series[x] for x in series.index if x.startswith("value_target")]
                target_ids = series[[x for x in series.index if (x.split("_")[0] in targets) and (x in _id_fields)]]
                links = defaultdict(list)
                for field, target_id in target_ids.items():
                    links[field].append(target_id)
                linked_to = [Obj.get_queryset(links) for Obj in object_list] 
                if cls._in_table(database_table, value_name, "measure", linked_to=linked_to):
                    if not cls._in_table(database_table, value_name, "measure", value, linked_to):
                        log.error("Line %d: Value mismatch, did not overwrite Value\
                                   Name %s Type %s value %s, linked to %s" % (idx, value_name, "measure", str(value), str(linked_to)))
                else:
                    if value_name not in model_cache:
                        model = cls.infer_type(value_name, "measure", value)
                        model_cache[value_name] = model
                    cls.create_value(value_name, "measure", value, linked_to, value_model=model_cache[value_name])


    @classmethod
    def add_metadata(cls, input_table, database_table, log=None):
        print("Adding metadata")
        # METADATA
        # Heuristics:
        # - Metadata can be attached to basically anything for any reason
        # - Grab all Objects referenced, then from theoretically smallest to largest table, search in those Objects for those Metadata linked to it
        # - If not found, make it and remove it from the proposed list
        _id_fields = id_fields()
        model_cache = {}
        for idx, series in input_table.iterrows():
            series = series.dropna()
            value_name = series["value_name"]
            value = series["value"]
            targets = [series[x] for x in series.index if x.startswith("value_target")]
            target_ids = series[[x for x in series.index if (x.split("_")[0] in targets) and (x in _id_fields)]]
            links = defaultdict(list)
            for field, target_id in target_ids.items():
                links[field].append(target_id)
            linked_to = [Obj.get_queryset(links) for Obj in object_list]
            if cls._in_table(database_table, value_name, "metadata", linked_to=linked_to):
                if not cls._in_table(database_table, value_name, "metadata", value, linked_to):
                    log.error("Line %d: Value mismatch, did not overwrite Value\
                               Name %s Type %s value %s, linked to %s" % (idx, value_name, "metadata", str(value), str(linked_to)))
            else:
                if value_name not in model_cache:
                    model = cls.infer_type(value_name, "metadata", value)
                    model_cache[value_name] = model
                cls.create_value(value_name, "metadata", value, linked_to, value_model=model_cache[value_name])

    @classmethod
    def _table_queryset(cls, table):
        queryset_list = []
        for Obj in object_list:
            fields = {}
            for field in Obj.get_value_fields() + Obj.get_id_fields():
                if field in table.columns.str.split(".").str.get(0):
                    unique_ids = table[table.columns[table.columns.str.startswith(field)]].melt().dropna()["value"].unique()
                    fields[field] = unique_ids.tolist()
            qs = Obj.get_queryset(fields)
            if qs.exists():
                queryset_list.append(qs)
        return queryset_list

    @classmethod
    def add_values(cls, table, log=None):
        print("Grabbing queryset from table")
        table_objects = cls._table_queryset(table)
        print("Grabbing all values from querysets")
        for value_type, add_function in [("parameter", cls.add_parameters),
                                         ("measure", cls.add_measures), 
                                         ("metadata", cls.add_metadata)]:
            all_vals = Value.objects.none()
            for obj_qs in table_objects:
                # Measure must be attached to a Result, so we can cut down on false positives and matrix size
                # Significantly by restricting measures to those attached to Results in the given table
                if (value_type != "measure") or ((value_type == "measure") and (obj_qs.model.base_name == "result")):
                    val_qs = Value.objects.filter(**{obj_qs.model.plural_name+"__in": obj_qs})
                    all_vals = all_vals | val_qs
            database_value_table = Value.queryset_to_table(all_vals, indexes=["pk"])
            names = table[table["value_type"]==value_type]["value_name"].unique()
            if len(names) == 0:
                continue
            add_function(table[table["value_type"]==value_type], database_value_table, log)

    def linked_to(self, queryset_list, only=True):
        #Queryset list is a list of querysets to check if they are linked
        # Check that every object in the list is linked to the value (and nothing else is)
        links = self.get_links()
        for qs in queryset_list:
            if (qs.model.plural_name not in links) and (qs.exists()):
                return False
            elif (qs.model.plural_name not in links):
                continue
            if only and len(qs) != len(links[qs.model.plural_name]):
                return False
            for _id in qs.values(qs.model.id_field).distinct():
                if _id[qs.model.id_field] not in links[qs.model.plural_name]:
                    return False
                else:
                    links[qs.model.plural_name].pop(links[qs.model.plural_name].index(_id[qs.model.id_field]))
        if only:
            for field in links:
                if len(links[field]) > 0:
                    return False
        return True

    def get_links(self):
        linked_to = [ (Obj.plural_name, Obj) for Obj in object_list if getattr(self, Obj.plural_name).exists() ]
        self_link_ids = {}
        for field, model in linked_to:
            ids = list(getattr(self, field).values_list(model.id_field, flat=True).distinct())
            self_link_ids[field] = ids
        return self_link_ids

    def related_values(self, name, value_type, linked_to, upstream=False, only=False):
        #Reach out to find each of the relevant related objects linked to
        #everything tied to this Value, and then search those sets
        records = [] # Format (self.name, self_value, name, val.content_object.value, B_id)
        self_links = self.get_links()
        self_value = self.content_object.value
        values = Value.objects.none()
        for link_field in linked_to:
            queryset = getattr(self, link_field).none()
            for field in self.linkable_objects:
                if field is not link_field:
                    search_set = getattr(self, field).all()
                    #TODO: make related_* functions handle QuerySets instead of just self
                    for obj in search_set:
                        queryset = queryset | obj.related_objects(link_field, upstream)
            if queryset.exists():
                model = queryset[0]._meta.model
                related_with_target = model.with_value(name, value_type,
                                         linked_to, queryset, upstream, only)
                if related_with_target != False:
                    for obj in related_with_target:
                        values = values | obj.get_values(name=name, value=value_type)
        return values

    def upstream_values(self, name, value_type, linked_to, only=False, include_self=True):
        # Search strictly upstream objects of the links of this one
        pass

    @classmethod
    def queryset_to_table(cls, value_queryset, indexes=None, additional_values=[]):
        values = ["pk", "name"]
        values.extend([Obj.plural_name + "__" + Obj.id_field for Obj in object_list])
        values.extend([Val.type_name + "__value" for Val in value_list])
        values.extend(additional_values)
        value_queryset = value_queryset.prefetch_related(*[Obj.plural_name for Obj in object_list])
        value_queryset = value_queryset.values(*values)
        table = pd.DataFrame.from_records(value_queryset)
        values.pop(values.index("pk"))
        values.pop(values.index("name"))
        values = [value for value in values if value in table.columns]
        if len(values) == 0:
            return pd.DataFrame()
        if isinstance(indexes, str):
            if indexes in values:
                values.pop(values.index(indexes))
        elif hasattr(indexes, '__iter__'):
            for ind in indexes:
                if ind in values:
                    values.pop(values.index(ind))
#            table = table.pivot(index=indexes, columns="name", values=values)
        # This is what happens when there are multiple values for a given key
        # and it must aggregate them
        # This is slower, but reserving the x.dropna() for when we know
        # there's more than one value in there speeds it up
        def agg_fun(x):
            if len(x) == 1:
                return set([str(x.values[0])]) if pd.notnull(x.values[0]) else np.nan
            elif len(x) > 1:
                x=x.dropna()
                if len(x) >=1:
                    return set([str(y) for y in x.values])
                else:
                    return np.nan
            else:
                return np.nan
        #for field in indexes:
        #    table[field] = table[field].fillna("")
        table = table.pivot_table(index=indexes, columns=["name"], values=values,
                                  aggfunc=agg_fun)
        return table.dropna(axis=1, how='all')

    @classmethod
    def _in_table(cls, table, value_name, value_type, value=None, linked_to=None):
        #Convert the queryset list into something easier to compare in a Pandas table
        linked_two = []
        for qs in linked_to:
            model = qs.model
            for obj in qs:
                linked_two.append((model, str(getattr(obj, model.id_field))))
        linked_to = linked_two
        # linked_to = [(Model, id), ...]
        # If value is not None, we will check to make sure that value is identical
        if value_name not in table.columns.get_level_values("name"):
            return False
        vname_table = table.xs(value_name, level="name", axis=1).dropna(axis=0, how='all')
        fields = defaultdict(set)
        for model, obj_id in linked_to:
            field = model.plural_name + "__" + model.id_field
            fields[field].add(obj_id)
        for field in fields:
            vname_table = vname_table.where(vname_table[field] == fields[field]).dropna(axis=0, how='all')
            if vname_table.empty:
                return False
        for Obj in object_list:
            field = Obj.plural_name + "__" + Obj.id_field
            if (field in vname_table) and (field not in fields):
                vname_table = vname_table.where(pd.isna(vname_table[field])).dropna(axis=0, how='all')
                if vname_table.empty:
                    return False
        if value is None:
            return True
        else:
            value_fields = vname_table.columns[vname_table.columns.str.contains("__value")]
            if len(value_fields) > 1:
                raise ValueError("Two value types found in database for %s %s" % (value_type, value_name))
            elif len(value_fields) == 0:
                raise ValueError("No value column for %s %s" % (value_type, value_name))
            else:
                value_field = value_fields[0]
            vname_table = vname_table.where(vname_table[value_field].apply(lambda x: (value in x) or (str(value) in x)))
            vname_table = vname_table.dropna(axis=1, how='all').dropna(axis=0, how='all')
            if vname_table.empty:
                return False
            if vname_table.shape[0] > 1:
                raise ValueError("Found two Values with the same signature: Type: %s, Name: %s, Value: %s, Links: %s" % (value_type, value_name, value, str(linked_to)))
            return True

    @classmethod
    def relate_value_sets(cls, A, B):
        # Link all Values in A to all Values in B, if possible
        pass

    @classmethod
    def disambiguate(cls, name, value_type=None, linked_to=None, only=False, return_queryset=False):
        #Like most functions, try to kick out as soon as we know there's an ambiguity we can resolve
        qs = Value.objects.filter(name=name)
        if value_type is not None:
            qs = qs.filter(type=value_type)
        qs = qs.prefetch_related("samples","features","analyses",
                                 "investigations","steps","processes","results")
        if linked_to is not None:
            if isinstance(linked_to, list):
                kwargs = {}
                for link in linked_to:
                    kwargs[link + "__isnull"] = False
                if only:
                    for obj in self.linkable_objects:
                        if obj + "__isnull" not in kwargs:
                            kwargs[obj + "__isnull"] = True
                qs = qs.filter(**kwargs)
            else:
                 kwargs = {linked_to + "__isnull": False}
                 if only:
                     for obj in self.linkable_objects:
                         if obj != linked_to:
                             kwargs[obj + "__isnull"] = True
                 qs = qs.filter(**kwargs)
        values = qs
        qs = qs.annotate(samples_count=models.Count("samples"),
                         features_count=models.Count("features"),
                         analyses_count=models.Count("analyses"),
                         investigations_count=models.Count("investigations"),
                         results_count=models.Count("results"),
                         processes_count=models.Count("processes"),
                         steps_count=models.Count("steps"))
        qs = qs.values("type","samples_count","features_count",
                       "analyses_count","investigations_count","results_count",
                       "processes_count","steps_count")
        qs = qs.distinct()
        #Unambiguous if 1 signature, or vacuously if not in DB at all
        if (len(qs) <= 1):
            if return_queryset:
                return values
            else:
                return True
        else:
            #Collect ambiguities
            if return_queryset:
                return values
            signatures = list(qs)
            signature_dict = defaultdict(set)
            for signature in signatures:
                link_list = []
                for key in signature:
                    if key.endswith("_count") and (signature[key]>0):
                        link_list.append(key.split("_")[0])
                if link_list:
                    signature_dict[signature["type"]].add(tuple(link_list))
            return signature_dict

    @classmethod
    def infer_type(cls, value_name, value_type, value=None):
        found_types = ContentType.objects.filter(pk__in=Value.objects.filter(name=value_name,
                                                 type=value_type).only("content_type").values("content_type")).distinct()
        if len(found_types) > 1:
            raise DuplicateTypeError("Two types found for value name %s of \
                                      type %s" % (self.id_field, self.vtype))
        elif len(found_types) == 1:
            if found_types[0].model_class() == None:
                raise ValueError("Retrieved a null model class for value name %s type %s" % (value_name, value_type))
            return found_types[0].model_class()
        elif value != None:
            strvalue = str(value)
            try:
                arrow.get(strvalue, cls.default_date_format)
                return DatetimeVal
            except arrow.parser.ParserError:
                pass
            try:
                uuid.UUID(strvalue)
                return ResultVal
            except ValueError:
                pass
            try:
                int(strvalue)
                return IntVal
            except ValueError:
                pass
            try:
                float(strvalue)
                return FloatVal
            except ValueError:
                pass
            # Default value
            return StrVal
        else:
            return None

    @classmethod
    def update_search_vector(self):
        Value.objects.update(
            search_vector= (SearchVector('name', weight='A') +
#                            SearchVector('', weight='B') +
                            SearchVector('type', weight='B'))
        )



