#Views for autocomplete

from dal import autocomplete

from db.models import *
from db.models.object import Object

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
