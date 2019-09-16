from collections import OrderedDict
from django_jinja_knockout.views import KoGridView, KoGridInline

from .models import Investigation, Sample, Step
from .forms import ProcessForm, SampleForm

class InvestigationGridView(KoGridView):
    model = Investigation
    grid_fields = "__all__"
    allowed_sort_orders = "__all__"

class EditableInvestigationView(KoGridInline, InvestigationGridView):
    search_fields = [
        ('description', 'icontains')
    ]
    client_routes = {
    }
    enable_deletion = True
#    form_with_inline_formsets = ClubForm

class SampleFkWidgetGrid(KoGridView):
    model = Sample
    form = SampleForm
    enable_deletion = True
    grid_fields = '__all__'
    allowed_sort_orders = '__all__'
#    search_fields = [
#        ('company_name', 'icontains'),
#    ]

class StepFkWidgetGrid(KoGridView):
    model = Step
    form = ProcessForm
    enable_deletion = False
    grid_fields = '__all__'
    allowed_sort_orders = '__all__'
    allowed_filter_fields = OrderedDict([
        ('name', 'icontains'),
        ('method', 'icontains')
    ])
