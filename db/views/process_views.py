# ----------------------------------------------------------------------------
# path: quorem/db/views/process_views.py
# authors: Mike Hall
# modified: 2022-06-20
# description: This file contains all views that related to processes.
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe

from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView

from ..models import *
from ..forms import ProcessDetailForm, ProcessCreateForm, ProcessFilterSet
from .generic_views import FilteredListView


class ProcessDetailView(DetailView):
    pk_url_kwarg = 'process_id'
    form = ProcessDetailForm
    queryset = Process.objects.all()
    template_name = "detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        obj = self.get_object()
        if len(obj.get_value_counts())>0:
            context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class ProcessFilterListView(FilteredListView):
    filterset_class = ProcessFilterSet
    template_name = "list.htm"
    model = Process
    paginate_by = 15

class ProcessCreateView(CreateView):
    form_class = ProcessCreateForm
    model = Process
    template_name = "create.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_name'] = "process"
        return context

class ProcessUpdateView(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'process_id'
    form = ProcessDetailForm
    def get_bs_form_opts(self):
        return {
            'title': 'Update Process',
            'submit_text': 'Save Process',
        }

    def get_success_url(self):
        return reverse('process_detail', kwargs={'process_id': self.object.pk})


