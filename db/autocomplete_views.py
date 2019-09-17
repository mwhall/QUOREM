#Views for autocomplete

from dal import autocomplete

from db.models import Value, Category

class ValueAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Value.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs

class CategoryAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Category.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs
