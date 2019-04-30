from collections import OrderedDict
from django_jinja_knockout.views import KoGridView, KoGridInline

from .models import BiologicalReplicate, Investigation, Sample, ProtocolStep
from .forms import ProtocolForm, ReplicateForm, SampleForm

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
class ReplicateFkWidgetGrid(KoGridView):
    model = BiologicalReplicate
    form = ReplicateForm
    enable_deletion = True
    grid_fields = '__all__'
    allowed_sort_orders = '__all__'

class ProtocolStepFkWidgetGrid(KoGridView):
    model = ProtocolStep
    form = ProtocolForm
    enable_deletion = False
    grid_fields = '__all__'
    allowed_sort_orders = '__all__'
    allowed_filter_fields = OrderedDict([
        ('name', 'icontains'),
        ('method', 'icontains')
    ])
