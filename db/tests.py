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

    #depends on test_investigation_form being run first.
    def test_sample_form(self):
        test_inv = models.Investigation(name='test', institution=
        'test', description='test')
        test_inv.save()
        form_data = {'name': 'test_Sample',
                     'investigation': 1}
        form = forms.SampleForm(data=form_data)
        print(form.errors)
        self.assertTrue(form.is_valid())
