from collections import defaultdict

from .register import object_list, value_list

def all_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if (x.name not in ["search_vector", "content_type", \
                     "all_upstream", "object_id", "category_of"]) and \
                     x.concrete] for Obj in object_list] for item in sublist]

def id_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if (x.name in ["id", "name", "uuid"]) and (x.concrete)] \
                         for Obj in object_list] for item in sublist]

def required_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name) \
                 for x in Obj._meta.get_fields() \
                     if x.name not in ["search_vector", "content_type", \
                                    "object_id", "category_of"] and x.concrete \
                     and hasattr(x,"blank") and not x.blank] \
                         for Obj in object_list] for item in sublist]

def reference_fields():
    # Returns tuples of the field name, from model, and to model
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, \
                                                      x.model, \
                                                      x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream", "content_type", \
                 "object_id", "category_of"] and x.concrete and x.is_relation] \
                 for Obj in object_list] for item in sublist]

def single_reference_fields():
    # Returns tuples of the field name, from model, and to model
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, \
                                                      x.model, \
                                                      x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream", "content_type", \
                 "object_id", "category_of"] and x.concrete and x.many_to_one] \
                 for Obj in object_list] for item in sublist]


def many_reference_fields():
    return [item for sublist in [ [(Obj.base_name+"_"+x.name, x.model, x.related_model) \
                 for x in Obj._meta.get_fields() if x.name not in \
                 ["values", "categories", "all_upstream"] \
                 and x.concrete and (x.many_to_many or x.one_to_many)] for Obj in object_list] \
                 for item in sublist]

def reference_proxies():
    proxies = defaultdict(list)
    for field, source_model, ref_model in reference_fields():
        if ref_model.base_name not in ["value", "category", "file"]:
            for proxy in ref_model.get_id_fields():
                proxies[field].append(proxy)
    return proxies
