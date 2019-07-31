from django.test import TestCase

from . import models, views, forms
from quorem.wiki import initialize_wiki

from selenium import webdriver
import os

def chromedriver_init():
    option = webdriver.ChromeOptions()
    option.add_argument("--headless")
    #driver_location = os.getcwd() + '/db/chromedriver'
    driver = webdriver.Chrome(chrome_options=option)
    return driver

#Note that functions with prefix "test_" will be run by manage.py test
class FunctionalTests(TestCase):
    def test_webdriver(self):
        driver = chromedriver_init()
        driver.get('http://localhost:8000')
        assert driver

#simply test if the basic forms work
class BasicFormTests(TestCase):
    #initialize objects into testdb to allow form tests.
    def setUp(self):
        initialize_wiki()
        test_inv = models.Investigation.objects.create(name="Test Inv.", institution='Test co.',
                                        description="A test.")
        test_sample = models.Sample.objects.create(name="T001", investigation_id=test_inv.pk)
        test_sampleMeta = models.SampleMetadata.objects.create(key='measure', value='measurement',
                                                                sample = test_sample)
        test_protocol = models.BiologicalReplicateProtocol.objects.create(name='test procedure',
                                                description='A test', citation="test et al")
        test_replicate = models.BiologicalReplicate.objects.create(name='TR001', sample=test_sample,
                            biological_replicate_protocol=test_protocol)

    def test_investigation_form(self):
        form_data = {'name': 'form_investigation',
                     'institution':'Testing Ltd.',
                     'description': "A simple test."}
        form = forms.InvestigationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_sample_form(self):
        test_inv = models.Investigation.objects.get(name="Test Inv.")
        form_data = {'name': 'test_Sample',
                     'investigation': test_inv.pk}
        form = forms.SampleForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_protocol_form(self):
        form_data = {'name': 'test',
                     'description': 'test',
                     'citation': 'test et al'}
        form = forms.ProtocolForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_replicate_form(self):
        test_inv = models.Investigation.objects.get(name="Test Inv.")
        test_sample = models.Sample.objects.get(name="T001")
        test_protocol = models.BiologicalReplicateProtocol.objects.get(name='test procedure')
        form_data = {'name': 'test2',
                     'sample': test_sample.pk,
                     'biological_replicate_protocol': test_protocol.pk}
        form = forms.ReplicateForm(data=form_data)
        self.assertTrue(form.is_valid())
