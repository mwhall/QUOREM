from django.test import TestCase, LiveServerTestCase, TransactionTestCase

from . import models, views, forms
from accounts.models import User
from quorem.wiki import initialize_wiki

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

def chromedriver_init():
    option = webdriver.ChromeOptions()
    option.add_argument("--headless")
    option.add_argument("--enable-javascript")
    """
    LOCAL TESTING:

    driver_location = os.getcwd() + '/db/chromedriver'
    driver = webdriver.Chrome(executable_path=driver_location, chrome_options=option)

    """
    #CircleCI config:
    driver = webdriver.Chrome(chrome_options=option)

    return driver

#Class seleniumTests instantiates web driver
class SeleniumTest(LiveServerTestCase):
    serialized_rollback=True
    def setUp(self):
        self.driver = chromedriver_init()
        self.driver.implicitly_wait(10)
        super(SeleniumTest, self).setUp()

    def tearDown(self):
        self.driver.quit()
        super(SeleniumTest, self).tearDown()

class SearchTest(SeleniumTest):
    #fixtures = ['testdump.json']
    pass
    """
    def test_searchpage(self):
        #init
        driver = self.driver
        wait = WebDriverWait(driver, 100)
        driver.get(self.live_server_url)
        #click signin page
        signup = driver.find_element_by_xpath('/html/body/header/div[1]/ul/li[1]/a')
        signup.click()
        #find form elements
        email = driver.find_element_by_id('id_email')
        password1 = driver.find_element_by_id('id_password')
        password2 = driver.find_element_by_id('id_confirm_password')
        submit = driver.find_element_by_xpath('/html/body/header/div[2]/form/div/button')
        #enter valid registration information and submit
        email.send_keys('testemail@gmail.com')
        password1.send_keys('password123')
        password2.send_keys('password123')
        #submit the form
        submit.click()
        #go to seach page
        driver.get(self.live_server_url + '/search/')
        #check that facets exist
        types =  driver.find_elements_by_class_name('typecounts')
        print("Testy woop de woop ", types[0].text)
        assert types != None
        driver.implicitly_wait(5)
        types[0].click()
        meta = driver.find_elements_by_class_name('metadata')
        assert meta != None
        print("TEST TEST TEST ", meta[1].text)
        driver.implicitly_wait(5)
        meta[1].click()

        NOTE: JS elements never load on circle for some reason.
        Completely stumped on this for now, so removing this particular facet of the tests.
        This test passes on local machine but not in circleci.
        move_slider = webdriver.ActionChains(driver)
        #slider = driver.find_element_by_xpath('//*[@id="slider-range"]/span[1]')
        slider = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="slider-range"]/span[1]' )))
#        slider = driver.find_elements_by_class_name('ui-slider-handle')
        assert slider != None
        move_slider.click_and_hold(slider).move_by_offset(10,0).release().perform()

        #search
        search = driver.find_element_by_xpath('/html/body/div/div[2]/div[1]/form/button')
        search.click()
        #check that search facets have happened
        category_filter = driver.find_element_by_class_name('btn-outline-primary')
        meta_filter = driver.find_element_by_class_name('btn-outline-success')
    #    range_filter = driver.find_element_by_class_name('btn-outline-warning')

        assert category_filter != None
        assert meta_filter != None
    #    assert range_filter != None

        meta_filter.click()
        category_filter = driver.find_elements_by_class_name('btn-outline-primary')
        meta_filter = driver.find_elements_by_class_name('btn-outline-success')
    #    range_filter = driver.find_elements_by_class_name('btn-outline-warning')

        assert len(category_filter) != 0
        assert len(meta_filter) == 0
        return True
        """
#simply test if the basic forms work
class BasicFormTests(TestCase):
    #initialize objects into testdb to allow form tests.
    def setUp(self):
        initialize_wiki()
        #create a test user
        user = User.objects.create(email="test@hotmail.com", username="testyboi")


        test_inv = models.Investigation.objects.create(name="Test Inv.", institution='Test co.',
                                        description="A test.")
        test_sample = models.Sample.objects.create(name="T001", investigation_id=test_inv.pk)
        test_category = models.ProcessCategory.objects.create(name='Test Process', description='test category')
        test_process = models.Process.objects.create(name="test P", citation="blep" , description="a test", category=test_category)
        test_step = models.Step.objects.create(name="step 1", method="do the step", description="step and walk")
        test_step.processes.add(test_process)


    def test_investigation_form(self):
        form_data = {'name': 'form_investigation',
                     'institution':'Testing Ltd.',
                     'description': "A simple test."}
        form = forms.InvestigationForm(data=form_data)
        self.assertTrue(form.is_valid())



#Note that functions with prefix "test_" will be run by manage.py test
class RegistrationTest(SeleniumTest):
    def test_register(self):
        driver = self.driver
        #nav to web page
        driver.get(self.live_server_url)
        #navigate to sign up page
        signup = driver.find_element_by_xpath('/html/body/header/div[1]/ul/li[1]/a')
        signup.click()
        #find form elements
        email = driver.find_element_by_id('id_email')
        password1 = driver.find_element_by_id('id_password')
        password2 = driver.find_element_by_id('id_confirm_password')
        submit = driver.find_element_by_xpath('/html/body/header/div[2]/form/div/button')
        #enter valid registration information and submit
        email.send_keys('testemail@gmail.com')
        password1.send_keys('password123')
        password2.send_keys('password123')
        #submit the form
        submit.click()
        #Try to enter the page.
        enter = driver.find_element_by_xpath('/html/body/header/div[2]/p/a')
        enter.click()
        assert "Investigation List" in driver.page_source
