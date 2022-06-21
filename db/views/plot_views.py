# ----------------------------------------------------------------------------
# path: quorem/db/views/plot_views.py
# authors: Mike Hall
# modified: 2022-06-21
# description: This file contains all views that are for making plots.
# ----------------------------------------------------------------------------

from django.shortcuts import render, redirect
from django.utils.html import format_html, mark_safe
from django.views.generic.base import TemplateView

from django.views.generic.edit import FormView

from ..plot import *
from ..models import *
from ..forms import *
from .generic_views import reverse

#Analysis portal view. Just a place holder for now
def analyze(request):
    return render(request, 'analyze/analyze.htm')

##Plot pages.
#Plotting landing page
def plot_view(request):
    return render(request, 'analyze/plot.htm')

class TaxBarSelectView(FormView):
    form_class = TaxBarSelectForm
    template_name = 'taxbarselect.htm'
    def post(self, request, *args, **kwargs):
        request.POST = request.POST.copy()
        samples = request.POST.getlist('samples','')
        if samples is not '':
            # Dict is immutable, so must copy
            # For some reason, any multi-selects lose all but the last element, 
            # so we pass it as a single string
            request.POST['samples'] = ",".join(request.POST.getlist('samples'))
        metadata_sort_by = request.POST.getlist('metadata_sort_by','')
        if metadata_sort_by is not '':
            request.POST['metadata_sort_by'] = ",".join(request.POST.getlist('metadata_sort_by'))
        return redirect(reverse('plot-tax-bar', post=request.POST))

class TreeSelectView(FormView):
    form_class = TreeSelectForm
    template_name = 'treeselect.htm'
    def post(self, request, *args, **kwargs):
        return redirect(reverse('plot-tree', post=request.POST))

#For feature correlation, re-use taxbar form.
class TaxCorrelationSelectView(FormView):
    form_class = TaxBarSelectForm
    template_name = 'analyze/correlation.htm'
    def post(self, request, *args, **kwargs):
        return redirect(reverse('plot-tax-correlation', post=request.POST))

class TreePlotView(TemplateView):
    template_name = "plot/treeplot.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tr = self.request.GET.get('tree_result','')
        feature_pks = self.request.GET.get('features','')
        show_names = self.request.GET.get('show_names','')
        show_names = False if show_names.lower() in ["", "false", "f", "no", "n", "0"] else True
        if feature_pks:
            feature_pks = [int(x) for x in feature_pks.split(",")]
        else:
            feature_pks = []
        plot = tree_plot(tr, feature_pks, show_names)
        context["plot_html"] = mark_safe(plot)
        return context

class TableCollapseView(FormView):
    template_name = "tablecollapse.htm"
    form_class = TableCollapseForm
    success_url = '/taxon-table/'

    def get_initial(self):
        initial = super().get_initial()
        initial['count_matrix'] = self.request.GET.get('count_matrix')
        initial['taxonomy_result'] = self.request.GET.get('taxonomy_result')
        initial['taxonomic_level'] = self.request.GET.get('taxonomic_level','genus').capitalize()
        initial['metadata_collapse'] = self.request.GET.get('metadata_collapse',None)
        initial['normalize_method'] = self.request.GET.get('normalize_method','proportion')
        return initial

    def form_valid(self, form):
        return redirect(reverse('tax_table_download'))

    def post(self, request, *args, **kwargs):
#        request.POST = request.POST.copy()
        #metadata_sort = request.POST.getlist('metadata_sort',None)
        #if metadata_sort != None:
        #    request.POST['metadata_sort'] = ",".join(request.POST.getlist('metadata_sort'))
        return redirect(reverse('tax_table_download'))

#    def get_context_data(self, **kwargs):
#        context = super().get_context_data(**kwargs)
#        cmr = self.request.GET.get('count_matrix','')
#        tr = self.request.GET.get('taxonomy_result','')
#        level = self.request.GET.get('taxonomic_level','genus')
#        metadata_collapse = self.request.GET.get('metadata_collapse',None)
#        metadata_sort = self.request.GET.get('metadata_sort',None)
#        normalize_method = self.request.GET.get('normalize_method','proportion')
#        if cmr and tr: #Minimum input to make a plot
#            plot_html = tax_bar_plot(tr, cmr, 
#                                     plot_height=plot_height,
#                                     level=level,
#                                     n_taxa=n_taxa,
#                                     normalize_method=normalize_method,
#                                     metadata_collapse=metadata_collapse,
#                                     metadata_sort=metadata_sort,
#                                     label_bars=label_bars).to_html()
#            context['plot_html'] = mark_safe(plot_html)
#        return context
#

class PCoAPlotView(FormView):
    template_name = "pcoaplot.htm"
    form_class = PCoAPlotForm

    def get_initial(self):
       initial = super().get_initial()
       initial['count_matrix'] = self.request.GET.get('count_matrix')
       initial['measure'] = self.request.GET.get('measure','braycurtis')
       initial['metadata_colour'] = self.request.GET.get('metadata_colour')
       initial['three_dimensional'] = self.request.GET.get('three_dimensional')
       return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cmr = self.request.GET.get('count_matrix','')
        measure = self.request.GET.get('measure','braycurtis')
        metadata_colour = self.request.GET.get('metadata_colour','')
        three_dimensional = self.request.GET.get('three_dimensional',False)
        if cmr: #Minimum input to make a plot
            plot_html = pcoa_plot(cmr,
                                  measure=measure,
                                  metadata_colour=metadata_colour,
                                  three_dimensional=three_dimensional).to_html()
            context['plot_html'] = mark_safe(plot_html)
        return context

class TablePlotView(FormView):
    template_name = "tableplot.htm"
    form_class = TablePlotForm

    def get_initial(self):
        initial = super().get_initial()
        initial['count_matrix'] = self.request.GET.get('count_matrix')
        initial['taxonomy_result'] = self.request.GET.get('taxonomy_result')
        initial['taxonomic_level'] = self.request.GET.get('taxonomic_level','genus').capitalize()
        initial['plot_height'] = int(self.request.GET.get('plot_height',750))
        initial['n_taxa'] = int(self.request.GET.get('n_taxa',10))
        initial['label_bars'] = bool(self.request.GET.get('label_bars',False))
        initial['metadata_collapse'] = self.request.GET.get('metadata_collapse',None)
        initial['metadata_sort'] = self.request.GET.getlist('metadata_sort',None)
        initial['normalize_method'] = self.request.GET.get('normalize_method','proportion')
        initial['plot_type'] = self.request.GET.get('plot_type','bar')
        return initial

    def get(self, request, *args, **kwargs):
        request.GET = request.GET.copy()
        print(dict(request.GET))
        if "metadata_collapse" in request.GET:
            if request.GET.get("metadata_collapse")=="" or request.GET.get("metadata_collapse")==None:
                request.GET.pop("metadata_collapse")
        print("GETTING TABLE PLOT")
        print(dict(request.GET))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cmr = self.request.GET.get('count_matrix','')
        tr = self.request.GET.get('taxonomy_result','')
        level = self.request.GET.get('taxonomic_level','genus')
        plot_height = int(self.request.GET.get('plot_height',1000))
        n_taxa = int(self.request.GET.get('n_taxa',10))
        label_bars = bool(self.request.GET.get('label_bars',False))
        metadata_collapse = self.request.GET.get('metadata_collapse',None)
        metadata_sort = self.request.GET.get('metadata_sort',None)
        normalize_method = self.request.GET.get('normalize_method','proportion')
        plot_type = self.request.GET.get('plot_type','bar')
        if cmr and tr: #Minimum input to make a plot
            plot_html = count_table_tax_plot(tr, cmr,
                                     plot_type=plot_type, 
                                     plot_height=plot_height,
                                     level=level,
                                     n_taxa=n_taxa,
                                     normalize_method=normalize_method,
                                     metadata_collapse=metadata_collapse,
                                     metadata_sort=metadata_sort,
                                     label_bars=label_bars).to_html()
            context['plot_html'] = mark_safe(plot_html)
        return context

class TaxBarPlotView(TemplateView):
    template_name = "taxbarplot.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tr = self.request.GET.get('taxonomy_result','')
        cmr = self.request.GET.get('count_matrix','')
        tl = self.request.GET.get('taxonomic_level','').lower()
        samples_from_investigation = self.request.GET.get('samples_from_investigation','')
        relative = self.request.GET.get('relative','')
        samples = self.request.GET.get('samples','')
        metadata_sort_by = self.request.GET.get('metadata_sort_by','')
        plot_height = self.request.GET.get('plot_height','')
        n_taxa = self.request.GET.get('n_taxa','')
        label_bars = self.request.GET.get('label_bars','')
        opt_kwargs = {}
        if samples != '':
            samples = samples.split(",")
            opt_kwargs["samples"] = [int(x) for x in samples]
        if tl != '':
            opt_kwargs["level"] = tl
        if relative != '':
            opt_kwargs["relative"] = False if relative.lower() in ["", "false", "f", "no", "n", "0"] else True
        if label_bars != '':
            opt_kwargs["label_bars"] = False if label_bars.lower() in ["", "false", "f", "no", "n", "0"] else True
        if plot_height != '':
            opt_kwargs["plot_height"] = int(plot_height)
        if n_taxa != '':
            opt_kwargs["n_taxa"] = int(n_taxa)
        if samples_from_investigation != '':
            opt_kwargs["samples_from_investigation"] = int(samples_from_investigation)
        if metadata_sort_by != "":
            metadata_sort_by = metadata_sort_by.split(",")
            opt_kwargs["metadata_sort_by"] = [int(x) for x in metadata_sort_by]
        print(opt_kwargs)
        plot_html = tax_bar_plot(tr,cmr,**opt_kwargs)
        context["plot_html"] = plot_html
        context["taxonomy_card"] = apps.get_model("db.Result").objects.get(pk=tr).bootstrap_card()
        context["matrix_card"] = apps.get_model("db.Result").objects.get(pk=cmr).bootstrap_card()
        return context

#plots correlation bewtween sample values and tax features.
class TaxCorrelationPlotView(TemplateView):
    template_name = "plot/taxcorrelationplot.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tr = self.request.GET.get('taxonomy_result','')
        cmr = self.request.GET.get('count_matrix','')
        tl = self.request.GET.get('taxonomic_level','').lower()
        relative = self.request.GET.get('relative','')
        opt_kwargs = {}
        if tl != '':
            opt_kwargs["level"] = tl
        if relative != '':
            opt_kwargs["relative"] = False if relative.lower() in ["", "false", "f", "no", "n", "0"] else True
        plot_html = tax_correlation_plot(tr,cmr,**opt_kwargs)
        context["plot_html"] = plot_html
        context["taxonomy_card"] = apps.get_model("db.Result").objects.get(pk=tr).bootstrap_card()
        context["matrix_card"] = apps.get_model("db.Result").objects.get(pk=cmr).bootstrap_card()
        return context

