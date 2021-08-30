from collections import defaultdict, OrderedDict

from django.db import models
from django.apps import apps
from django import forms
from django.utils.html import mark_safe, format_html

#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.contenttypes.models import ContentType
from db.models.object import Object

from combomethod import combomethod

class Process(Object):
    base_name = "process"
    plural_name = "processes"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ffd4d4'}

    description = "A set of Steps run with a typical series of Parameters"

    has_upstream = True

    name = models.CharField(max_length=255, unique=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name="downstream", blank=True)
    all_upstream = models.ManyToManyField('self', symmetrical=False, related_name='all_downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="processes", blank=True)

    def get_parameters(self, steps=None, step_field="pk"):
        Parameter = apps.get_model("db.Parameter")
        if steps is None:
            steps = self.steps.all()
#        else:
#            steps = self.steps.filter(pk__in=steps)
        params = {}
        for step in steps:
            proc_params = dict([(x.signature.get().name,
                                (x, 'process'))
                                for x in self.values.instance_of(Parameter).filter(steps=step, results__isnull=True, analyses__isnull=True)])
            step_params = step.get_parameters()[step.pk]
            proc_params.update(step_params)
            if not proc_params:
                proc_params = {}
            params[getattr(step, step_field)] = proc_params
        return params

    def auto_add_steps(self):
        source_steps = apps.get_model("db.Step").objects.filter(pk__in=self.analyses.values("results__source_step__pk"))
        self.steps.add(*source_steps)

    def add_steps(self, steps):
        self.steps.add(*apps.get_model("db.Step").objects.filter(pk__in=steps))

    @classmethod
    def get_crud_form(cls):
        CrudForm = super().get_crud_form()
        class CustomMMChoiceField(forms.ModelMultipleChoiceField):
            def label_from_instance(self, obj):
                count = obj.results.values("source_step").distinct().count()
                return "%s (%d %s)" % (obj.name, count, "Step" if (count==1) else "Steps")
        class ProcessCrudForm(CrudForm):
            steps = forms.ModelMultipleChoiceField(queryset=apps.get_model("db.Step").objects.all(),
                                                   label="Add/Remove Steps Individually",
                                                   required=False)
            analyses = CustomMMChoiceField(queryset=apps.get_model("db.Analysis").objects.all(),
                                           label="Add Steps from Analyses",
                                           required=False)
            def __init__(self, *args, **kwargs):
                if 'instance' in kwargs:
                    kwargs['initial'] = {'steps': [x.pk for x in kwargs['instance'].steps.all()]}
                super().__init__(*args, **kwargs)
            def save(self, commit=True):
                instance = super().save(commit=False)
                instance.steps.set(self.cleaned_data['steps'])
                for analysis in self.cleaned_data['analyses']:
                    instance.steps.add(*analysis.results.values_list("source_step", flat=True))
                if commit:
                    instance.save()
                return instance

            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'all_upstream', 'upstream']

        return ProcessCrudForm

    def html_steps(self):
        step_count = self.steps.count()
        accordions = {'steps': {'heading': format_html('Show Steps ({})', str(step_count))}}
        content = ""
        for step in self.steps.all():
            content += format_html("{}<BR/>", mark_safe(str(step)))
        accordions['steps']['content'] = content
        return self._make_accordion("steps", accordions)

    @classmethod
    def get_display_form(cls):
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            step_accordion = forms.CharField(label="Steps")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values', 'all_upstream']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['step_accordion'] = mark_safe(kwargs['instance'].html_steps())
                super().__init__(*args, **kwargs)
                self.fields = OrderedDict(self.fields)
                self.fields.move_to_end("value_accordion")
                self.fields.move_to_end("graph")
        return DisplayForm

    @classmethod
    def update_search_vector(cls):
        sv = (SearchVector('name', weight='A') +
                        SearchVector('values__signature__name', weight='B') +
                        SearchVector('values__signature__data', weight='C')

        )
        cls.objects.update(
            search_vector= sv
        )


    def related_steps(self, upstream=False):
        steps = self.steps.all()
        if upstream:
            steps = steps | apps.get_model("db", "Step").objects.filter(pk__in=steps.values("all_upstream").distinct())
        return steps

    def related_analyses(self):
        return self.analyses.all()
