# ----------------------------------------------------------------------------
# path: quorem/db/forms/fields.py
# authors: Mike Hall
# modified: 2022-06-14
# description: This file contains all custom fields used in QUOREM forms
# ----------------------------------------------------------------------------

from django import forms
from django.db.models import Case, When

# Used in certain django-autocomplete-light fields where order matters
# (e.g., selecting metadata categories for sorting, the order of those
#  categories matters and needs to be captured and preserved)

# Source: https://stackoverflow.com/questions/10296333/django-multiplechoicefield-does-not-preserve-order-of-selected-values

class OrderedModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def clean(self, value):
        qs = super(OrderedModelMultipleChoiceField, self).clean(value)
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(value)])
        return qs.filter(pk__in=value).order_by(preserved)

