from django.test import TestCase, LiveServerTestCase, TransactionTestCase
from .model_factories import *
from db.models import *


class BasicModelTestCase(TestCase):
    def test_investigation(self):
        inv = InvestigationFactory()
        assert(Investigation.objects.all())
