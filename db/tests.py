from django.test import TestCase

from . import models, views, forms
# Create your tests here.
class BasicFormTests(TestCase):
    def test_investigation_form(self):
        form_data = {'name': 'test_inv',
                     'institution':'Testing Ltd.',
                     'description': "A simple test."}
        form = forms.InvestigationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
