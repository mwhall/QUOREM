# ----------------------------------------------------------------------------
# path: quorem/db/forms/sample_views.py
# authors: Mike Hall
# modified: 2022-06-21
# description: This file contains all views that are for samples.
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView

from ..models import *
from ..forms import SampleDetailForm, SampleFilterSet
from .generic_views import FilteredListView

class SampleDetailView(DetailView):
    pk_url_kwarg = 'sample_id'
    form = SampleDetailForm
    queryset = Sample.objects.all()
    template_name = "detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        context['features_html'] = mark_safe(self.get_object().html_features())
        context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class SampleFilterListView(FilteredListView):
    filterset_class = SampleFilterSet
    template_name = "list.htm"
    model = Sample
    paginate_by = 15

class SampleCreate(CreateView):
    format_view_title = True
    form = SampleDetailForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Sample'}
    def get_heading(self):
        return "Create New Sample"

class SampleUpdate(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'sample_id'
    form = SampleDetailForm
    def get_bs_form_opts(self):
        return {
            'title': 'Edit Sample',
            'submit_text': 'Save Sample'
        }

