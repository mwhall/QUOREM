# ----------------------------------------------------------------------------
# path: quorem/db/views/step_views.py
# authors: Mike Hall
# modified: 2022-06-16
# description: This file contains all views that are for steps.
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView

from ..models import *
from ..forms import StepDetailForm, StepFilterSet
from .generic_views import FilteredListView

class StepDetailView(DetailView):
    pk_url_kwarg = 'step_id'
    form = StepDetailForm
    queryset = Step.objects.all()
    template_name = "detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        obj = self.get_object()
        if len(obj.get_value_counts())>0:
            context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class StepFilterListView(FilteredListView):
    filterset_class = StepFilterSet
    template_name = "list.htm"
    model = Step
    paginate_by = 15

class StepCreateView(CreateView):
    format_view_title = True
    form = StepDetailForm
    template_name = "core/custom_cbv_edit_inline.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = "create"
        return context
    def get_bs_form_opts(self):
        return {'submit_text': 'Save Step'}
    def get_heading(self):
        return "Create New Step"

class StepUpdateView(UpdateView):
    format_view_title = True
    pk_url_kwarg = 'step_id'
    form = StepDetailForm
    def get_bs_form_opts(self):
        return {
            'title': 'Update Step',
            'submit_text': 'Save Step',
        }

    def get_success_url(self):
        return reverse('step_detail', kwargs={'step_id': self.object.pk})

