# ----------------------------------------------------------------------------
# path: quorem/db/forms/result_views.py
# authors: Mike Hall
# modified: 2022-06-16
# description: This file contains all views that are related to results.
# ----------------------------------------------------------------------------

from django.utils.html import format_html, mark_safe

from django.views.generic.edit import FormView, CreateView, UpdateView
from django.views.generic.detail import DetailView

from ..models import *
from ..forms import ResultDetailForm, ResultFilterSet
from .generic_views import FilteredListView

class ResultDetailView(DetailView):
    pk_url_kwarg = 'result_id'
    form = ResultDetailForm
    queryset = Result.objects.all()
    template_name = "result_detail.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        #Add to context dict to make available in template
        obj = self.get_object()
        context['samples_html'] = mark_safe(obj.html_samples())
        #context['features_html'] = mark_safe(obj.html_features())
        if obj.has_value('qiime2_type'):
            context['provenance_graph'] = mark_safe(obj.simple_provenance_graph().pipe().decode().replace("<svg ", "<svg id=\"provenancegraph\" class=\"img-fluid\" ").replace("\n",""))
            stream_graph = obj.get_stream_graph()
            try:
                stream_graph = stream_graph.pipe()
                context['stream_graph'] = mark_safe(stream_graph.decode().replace("<svg ", "<svg id=\"streamgraph\" class=\"img-fluid\" ").replace("\n", ""))
            except:
                print("Stream graph failed to load")
        #context['values_html'] = mark_safe(obj.html_values())
        context['has_uploaded_file'] = obj.has_value("uploaded_spreadsheet") | obj.has_value("uploaded_artifact")
        context['filetype'] = obj.get_result_type()
        return context

class ResultFilterListView(FilteredListView):
    filterset_class = ResultFilterSet
    template_name = "list.htm"
    model = Result
    paginate_by = 15


