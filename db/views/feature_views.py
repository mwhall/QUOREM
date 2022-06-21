# ----------------------------------------------------------------------------
# path: quorem/db/views/feature_views.py
# authors: Mike Hall
# modified: 2022-06-16
# description: This file contains all views that are related to features.
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe

from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.detail import DetailView

from ..models import *
from ..forms import FeatureDetailForm, FeatureFilterSet
from .generic_views import FilteredListView


class FeatureDetailView(DetailView):
    pk_url_kwarg = 'feature_id'
    form = FeatureDetailForm
    queryset = Feature.objects.all()
    template_name = "feature_detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        context['samples_html'] = mark_safe(self.get_object().html_samples())
    #    context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class FeatureFilterListView(FilteredListView):
    filterset_class = FeatureFilterSet
    template_name = "list.htm"
    model = Feature
    paginate_by = 15
#    def get_context_data(self, **kwargs):
#        context = super().get_context_data(**kwargs)
#        context['base_name'] = self.model.base_name
        
#        return context

class FeatureCreate(CreateView):
    format_view_title = True
    form = FeatureDetailForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Feature'}
    def get_heading(self):
        return "Create New Feature"


