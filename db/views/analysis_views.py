# ----------------------------------------------------------------------------
# path: quorem/db/views/analysis_views.py
# authors: Mike Hall
# modified: 2022-06-16
# description: This file contains all analysis related views
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe
from django.http import HttpResponseRedirect
from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView

from .generic_views import reverse, FilteredListView
from ..models import Analysis
from ..forms import AnalysisDetailForm, AnalysisSelectForm, AnalysisCreateForm, AnalysisFilterSet

class AnalysisDetailView(DetailView):
    pk_url_kwarg = 'analysis_id'
    form = AnalysisDetailForm
    queryset = Analysis.objects.all()
    template_name = "analysis_detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        context['results_html'] = mark_safe(self.get_object().html_results())
        context['values_html'] = mark_safe(self.get_object().html_values())
        return context

class AnalysisCreateView(CreateView):
    form_class = AnalysisCreateForm
    model = Analysis
    template_name = "create.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_name'] = "analysis"
        return context

class AnalysisSelectView(FormView):
    form_class = AnalysisSelectForm
    template_name = 'analysis_select.htm'
    def form_valid(self, form):
        self.analysis_pk = self.request.POST.get("analysis")
        return HttpResponseRedirect(self.get_success_url())
    def get_success_url(self):
        return reverse('upload_to_analysis', kwargs={"analysis_id": self.analysis_pk})

class AnalysisFilterListView(FilteredListView):
    filterset_class = AnalysisFilterSet
    template_name = "list.htm"
    model = Analysis
    paginate_by = 15

