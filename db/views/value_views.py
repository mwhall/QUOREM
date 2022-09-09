# ----------------------------------------------------------------------------
# path: quorem/db/views/value_views.py
# authors: Mike Hall
# modified: 2022-09-08
# description: This file contains all views that are for Value objects.
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView
from django.db.models import Count

from ..models import *
from ..forms import ValueDetailForm, ValueFilterSet
from .generic_views import FilteredListView

class ValueDetailView(DetailView):
    pk_url_kwarg = 'value_id'
    form = ValueDetailForm
    queryset = Value.objects.all()
    template_name = "value_detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['signature'] = obj.signature.get()
        context['data'] = obj.data.get()
        #Add to context dict to make available in template
#        if len(obj.get_value_counts())>0:
#            context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class ValueFilterListView(FilteredListView):
    filterset_class = ValueFilterSet
    template_name = "value_list.htm"
    model = Value
    paginate_by = 15
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_obj'].object_list = context['page_obj'].object_list.annotate(results_count=Count('results'))
        return context


# This is all placeholder
class ValueCreateView(CreateView):
    format_view_title = True
    form = ValueDetailForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Step'}
    def get_heading(self):
        return "Create New Step"

class ValueUpdateView(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'value_id'
    form = ValueDetailForm
    def get_bs_form_opts(self):
        return {
            'title': 'Update Step',
            'submit_text': 'Save Step',
        }

    def get_success_url(self):
        return reverse('value_detail', kwargs={'value_id': self.object.pk})

