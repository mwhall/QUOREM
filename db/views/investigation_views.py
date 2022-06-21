# ----------------------------------------------------------------------------
# path: quorem/db/forms/investigation_views.py
# authors: Mike Hall
# modified: 2022-06-20
# description: This file contains all views that are related to investigations
# ----------------------------------------------------------------------------

from django.utils.html import mark_safe

from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.detail import DetailView

from ..models import *
from ..forms import InvestigationDetailForm, InvestigationFilterSet, InvestigationCreateForm
from .generic_views import FilteredListView 

class InvestigationDetailView(DetailView):
    pk_url_kwarg = 'investigation_id'
    form = InvestigationDetailForm
    queryset = Investigation.objects.all()
    template_name = "detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        obj = self.get_object()
        if len(obj.get_value_counts())>0:
            context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class InvestigationFilterListView(FilteredListView):
    filterset_class = InvestigationFilterSet
    template_name = "list.htm"
    model = Investigation
    paginate_by = 15

class InvestigationCreateView(CreateView):
    form_class = InvestigationCreateForm
    model = Investigation
    template_name = "create.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_name'] = "investigation"
        return context

class InvestigationUpdateView(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'investigation_id'
    form = InvestigationDetailForm
    def get_bs_form_opts(self):
        return {
            'title': 'Edit Investigation',
            'submit_text': 'Save Investigation'
        }

