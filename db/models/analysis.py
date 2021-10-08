from collections import defaultdict, OrderedDict
from django import forms
from django.db import models
from django.apps import apps
from django.utils.html import mark_safe, format_html
#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.contenttypes.models import ContentType
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from db.models.object import Object
from combomethod import combomethod

class Analysis(Object):
    base_name = "analysis"
    plural_name = "analyses"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffb37f'}

    description = "An Analysis represents an instantiation of a Process and its Steps, and optionally extra steps"

    # This is an instantiation/run of a Process and its Steps
    name = models.CharField(max_length=255)
    process = models.ForeignKey('Process', on_delete=models.CASCADE, related_name='analyses')
    # Run-specific parameters can go in here, but I guess Measures can too
    values = models.ManyToManyField('Value', related_name='analyses', blank=True)

    @classmethod
    def update_search_vector(cls):
        sv = (SearchVector('name', weight='A') +
                        SearchVector('values__signature__name', weight='B') +
                        SearchVector('values__signature__data', weight='C')

        )
        cls.objects.update(
            search_vector= sv
        )

    def get_parameters(self, steps=None, step_field="pk"):
        Parameter = apps.get_model("db.Parameter")
        if steps is None:
            steps = self.process.steps.all()
#        else:
#            steps = self.process.steps.filter(pk__in=steps)
        params = {}
        for step in steps:
            anal_params = dict([(x.signature.get().name,
                                (x, 'analysis'))
                                for x in self.values.instance_of(Parameter).filter(steps=step)])
            proc_params = self.process.get_parameters(steps=step.qs())[step.pk]
            anal_params.update(proc_params)
            if not anal_params:
                anal_params = {}
            params[getattr(step,step_field)] = anal_params
        return params

    def html_results(self):
        result_count = self.results.count()
        accordions = {'results': {'heading': format_html('Show Results ({})', str(result_count))}}
        content = ""
        for result in self.results.all():
            content += format_html("{}<BR/>", mark_safe(str(result)))
        accordions['results']['content'] = content
        return self._make_accordion("results", accordions)

    @classmethod
    def get_display_form(cls):
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            result_accordion = forms.CharField(label="Results")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['result_accordion'] = mark_safe(kwargs['instance'].html_results())
                super().__init__(*args, **kwargs)
                self.fields.move_to_end("value_accordion")
        return DisplayForm

    def related_samples(self, upstream=False):
        # All samples for all Results coming out of this Analysis
        samples = apps.get_model("db", "Sample").objects.filter(pk__in=self.results.values("samples").distinct())
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_steps(self, upstream=False):
        steps = self.extra_steps.all() | self.process.steps.all()
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_processes(self, upstream=False):
        results = apps.get_model("db", "Process").objects.filter(pk=self.process.pk)
        if upstream:
            processes = processes | apps.get_model("db", "Process").objects.filter(pk__in=processes.values("all_upstream").distinct())
        return processes

    def related_results(self, upstream=False):
        results = self.results.all()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

    def html_results_list(self):
        html_val = '<ul class="list-group">'
        artifact_html = {True:'', False:''}
        for result in self.results.all():
            step_name = result.source_step.name
            if result.has_value("uploaded_artifact"):
                has_file = True
                filetype = "artifact"
            elif result.has_value("uploaded_spreadsheet"):
                has_file = True
                filetype = "spreadsheet"
            else:
                has_file = False
                filetype = "artifact"
            if has_file:
                href = 'href="/data-%s?result_id=%d"' % (filetype, result.pk,)
                badge_type = 'success'
                button_class = "btn-outline-success"
                available_str = 'This <a class="badge badge-primary badge-pill" href="/result/%d/">%s</a>, a %s from Step %s, is archived and available for download' % (result.pk, filetype.capitalize(), result.get_result_type(),step_name)
            else:
                href='href="#"'
                badge_type = 'secondary'
                button_class = "btn-outline-secondary"
                available_str = 'This <a class="badge badge-primary badge-pill" href="/result/%d/">%s</a>, a %s from Step %s, has not been archived.' % (result.pk, filetype.capitalize(), result.get_result_type(), step_name)
            artifact_html[has_file] += '<li class="list-group-item d-flex justify-content-between align-items-center">'
            artifact_html[has_file] += '<div>'
            artifact_html[has_file] += '<button class="btn %s" type="button" data-toggle="collapse" data-target="#result%s" aria-expanded="false" aria-controls="result%s">%s &nbsp; <i class="fas fa-chevron-down"></i></button><br/>' % (button_class, result.pk, result.name, result.human_short())
            artifact_html[has_file] += '<div class="collapse" id="result%s">' % (result.pk,)
            artifact_html[has_file] += '<div class="card-body">'
            artifact_html[has_file] += available_str
            artifact_html[has_file] += '</div></div></div>'
            artifact_html[has_file] += '<a class="badge badge-%s badge-pill" %s><i class="fas fa-file-download"></i></a></li>' % (badge_type, href)
        html_val += artifact_html[True]
        html_val += artifact_html[False]
        html_val += "</ul>"
        return mark_safe(html_val)

    @classmethod
    def get_detail_view(cls, as_view=False):
        class AnalysisDetailView(DetailView):
            pk_url_kwarg = 'analysis_id'
            form = cls.get_display_form()
            queryset = cls.objects.all()
            template_name = "analysis_detail.htm"
            def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                #Add to context dict to make available in template
                context['results_html'] = mark_safe(self.get_object().html_results())
                context['values_html'] = mark_safe(self.get_object().html_values())
                return context
        if as_view:
            return AnalysisDetailView.as_view()
        else:
            return AnalysisDetailView



