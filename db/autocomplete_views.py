#Views for autocomplete
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html, mark_safe

from dal import autocomplete, forward

from db.models import *
from db.models.object import Object
from db.models.value import *

class ValueAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        return [x.base_name.capitalize() for x in Value.get_value_types()]

class CategoryAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Category.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs

class ObjectAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        return [x.base_name.capitalize() for x in Object.get_object_types()]

class SampleToFeatureAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Feature.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs

def object_relation_view_factory(from_object, to_object):
    from_object = Object.get_object_types(type_name=from_object)
    to_object = Object.get_object_types(type_name=to_object)

    class ObjectToObjectAutocomplete(autocomplete.Select2QuerySetView):
        def get_queryset(self):
            qs = to_object.objects.all()
            if self.q:
                qs = qs.filter(name__istartswith(self.q))
            return qs

    ObjectToObjectAutocomplete.__name__ = from_object.base_name.capitalize() + "To" + to_object.base_name.capitalize() + "Autocomplete"
    ObjectToObjectAutocomplete.__qualname__ = ObjectToObjectAutocomplete.__name__
    return ObjectToObjectAutocomplete

#Register these at top level
for ObjA in Object.get_object_types():
    for ObjB in Object.get_object_types():
        generated_class = object_relation_view_factory(ObjA.base_name, ObjB.base_name)
        globals()[generated_class.__name__] = generated_class

def object_autocomplete_factory(object_name):
    obj = Object.get_object_types(type_name=object_name)

    class ObjectAutocomplete(autocomplete.Select2QuerySetView):
        def get_queryset(self):
            count_matrix = self.forwarded.get("count_matrix",None)
            qs = obj.objects.all()
            if self.q:
                qs = qs.filter(name__icontains=self.q)
            pk = self.forwarded.get('pk', None)
            if pk:
                pks = pk.split(",")
                pks = [int(x) for x in pks]
                qs = qs.filter(pk__in=pks)
            if count_matrix:
                qs = qs.filter(pk__in=Result.objects.get(pk=count_matrix).related_samples())
            return qs.distinct()
        def get_result_label(self, item):
            return mark_safe(format_html(item.name))

    ObjectAutocomplete.__name__ = obj.base_name.capitalize() + "Autocomplete"
    ObjectAutocomplete.__qualname__ = ObjectAutocomplete.__name__
    return ObjectAutocomplete

for Obj in Object.get_object_types():
    generated_class = object_autocomplete_factory(Obj.base_name)
    globals()[generated_class.__name__] = generated_class

class TreeResultAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Result.objects.filter(values__signature__name="newick")
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.distinct()
    def get_result_label(self, item):
        return mark_safe(format_html('<b>Result {}</b>, UUID {}, <b>Analysis</b>: {}, <b>Source Step</b>: {}', item.pk, item.name, item.analysis.name, item.source_step.name))

class TaxonomyResultAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Result.objects.filter(values__signature__name="taxonomic_classification")
        if self.q:
            qs = qs.filter(name__icontains=self.q) | qs.filter(analysis__name__icontains=self.q)
        return qs.distinct()
    def get_result_label(self, item):
        return mark_safe(format_html('<b>Result {}</b>, UUID {}, <b>Analysis</b>: {}', item.pk, item.name, item.analysis.name))


class CountMatrixAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        taxonomy_result = self.forwarded.get("taxonomy_result", None)
        self.matrix_ct = ContentType.objects.get_for_model(Matrix)
        qs = Result.objects.filter(values__signature__value_type=self.matrix_ct)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        if taxonomy_result:
            tr = Result.objects.get(pk=taxonomy_result)
            qs = qs.filter(analysis=tr.analysis)
        return qs.distinct()
    def get_result_label(self, item):
        return mark_safe(format_html('<b>Result {}</b>, UUID {}, Produced by {}', item.pk, item.name, item.source_step.name))

class DataSignatureAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = DataSignature.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.distinct()

class TaxonomicLevelAutocomplete(autocomplete.Select2ListView):
    def get_list(self):
        return [x.capitalize() for x in ["kingdom","phylum","class","order","family","genus","species"]]
