from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.forms.utils import flatatt
from django.utils.html import format_html, mark_safe
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.aggregates import StringAgg

from celery import current_app

from quorem.wiki import refresh_automated_report

User = get_user_model()


class Investigation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255)
    description = models.TextField()

    values = models.ManyToManyField('Value', related_name="investigations", blank=True)
    categories = models.ManyToManyField('Category', related_name='investigations', blank=True)
    #Stuff for searching
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('investigation_detail', kwargs={'investigation_id': self.pk})}), self.name))

    #override save to update the search vector field
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        sv =( SearchVector('name', weight='A') +
             SearchVector('description', weight='B') +
             SearchVector('institution', weight='C') )
        Investigation.objects.update(search_vector = sv)
#        refresh_automated_report("investigation")
#        refresh_automated_report("investigation", pk=self.pk)

class Feature(models.Model):
    name = models.CharField(max_length=255, verbose_name="Name")
    sequence = models.TextField(null=True, blank=True)
    annotations = models.ManyToManyField('Value', related_name='annotations', blank=True)
    first_discovered_in = models.ForeignKey('Result', on_delete=models.CASCADE, blank=True, null=True)
    observed_results = models.ManyToManyField('Result', related_name='observed_results', blank=True, null=True)
    observed_samples = models.ManyToManyField('Sample', related_name='observed_samples', blank=True, null=True)

    values = models.ManyToManyField('Value', related_name="features", blank=True)
    categories = models.ManyToManyField('Category', related_name="features", blank=True)

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('feature_detail', kwargs={'feature_id': self.pk})}), self.name))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        Feature.objects.update(
            search_vector = (SearchVector('name', weight= 'A') +
                             SearchVector(StringAgg('annotations__str', delimiter=' '), weight='B'))
        )


class Sample(models.Model):
    """
    Uniquely identify a single sample (i.e., a physical sample taken at some single time and place)
    """
    name = models.CharField(max_length=255,unique=True)
    investigations = models.ManyToManyField('Investigation', related_name='samples', blank=True)  # fk 2
    analysis = models.ForeignKey('Analysis', related_name='samples', on_delete=models.CASCADE, blank=True)
    source_step = models.ForeignKey('Step', related_name='samples', on_delete=models.CASCADE, blank=True, null=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="samples", blank=True)
    categories = models.ManyToManyField('Category', related_name='samples', blank=True)
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('sample_detail', kwargs={'sample_id': self.pk})}), self.name))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        Sample.objects.update(
            search_vector = (SearchVector('name', weight= 'A') #+
                             # Should be investigation name, not pk.
                             # SearchVector('investigation', weight = 'B')
                             )
        )
#        refresh_automated_report("sample", pk=self.pk)

   

class Process(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    citation = models.TextField(blank=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name="downstream", blank=True)

    parameters = models.ManyToManyField('Value', related_name="processes", blank=True)
    categories = models.ManyToManyField('Category', related_name="processes", blank=True)

    search_vector = SearchVectorField(null=True)
    def __str__(self):
        return self.name

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('process_detail', kwargs={'process_id': self.pk})}), self.name))


    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        Process.objects.update(
            search_vector = (SearchVector('name', weight='A') +
                             SearchVector('citation', weight='B') +
                             SearchVector('description', weight='C') +
                             SearchVector('category__name', weight='D'))
        )


class Step(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    processes = models.ManyToManyField('Process', related_name='steps', blank=True)

    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)
    parameters = models.ManyToManyField('Value', related_name='steps', blank=True)
    categories = models.ManyToManyField('Category', related_name='steps', blank=True)
    search_vector = SearchVectorField(null=True)

    def __str__(self):
        return '%s' % (self.name,)

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('step_detail', kwargs={'step_id': self.pk})}), self.name))

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        Step.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('description', weight='B'))
        )

class Analysis(models.Model):
    # This is an instantiation/run of a Process and its Steps
    name = models.CharField(max_length=255)
    date = models.DateTimeField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    # If this is blank, then all the steps must be stored in extra_steps
    # But if the Process changes: 
    #  - all the Results with this Process must have their Parameters checked, and if they are the same, make sure it's only stored at the highest level
    #    but if it's different, specify it in the Result's Parameters
    #  - Analysis is 
    process = models.ForeignKey('Process', on_delete=models.CASCADE, blank=True)
    # Just in case this analysis had any extra steps, they can be defined and tagged here
    # outside of a Process
    extra_steps = models.ManyToManyField('Step', blank=True, null=True)
    # Run-specific parameters can go in here, but I guess Measures can too
    values = models.ManyToManyField('Value', related_name='analyses', blank=True, null=True)
    categories = models.ManyToManyField('Category', related_name='analyses', blank=True)
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_detail_link(self):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('analysis_detail', kwargs={'analysis_id': self.pk})}), self.name))


    @classmethod
    def update_search_vector(self):
        Analysis.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('date', weight='B') +
                            SearchVector('location', weight='C'))
        )


class Result(models.Model):
    """
    Some kind of result from an analysis
    """
    list_display = ('source', 'type', 'source_step', 'processes', 'samples', 'parameters', 'uuid')
    uuid = models.UUIDField(unique=True) #For QIIME2 results, this is the artifact UUID
    input_file = models.ForeignKey('UploadInputFile', on_delete=models.CASCADE, verbose_name="Result File Name", blank=True, null=True)
    source = models.CharField(max_length=255, verbose_name="Source Software/Instrument", blank=True, null=True)
    type = models.CharField(max_length=255, verbose_name="Result Type", blank=True, null=True)
    analysis = models.ForeignKey('Analysis', related_name='results', on_delete=models.CASCADE)
    # This process result is from this step
    source_step = models.ForeignKey('Step', on_delete=models.CASCADE, verbose_name="Source Step", blank=True, null=True)
    # Samples that this thing is the result for
    samples = models.ManyToManyField('Sample', related_name='results', verbose_name="Samples", blank=True)
    features = models.ManyToManyField('Feature', related_name='results', verbose_name="Features", blank=True)
    upstream = models.ManyToManyField('self', symmetrical=False, related_name='downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="results", blank=True)
    categories = models.ManyToManyField('Category', related_name='results', blank=True)

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.uuid)

    def get_detail_link(self, label='uuid'):
        return mark_safe(format_html('<a{}>{}</a>', flatatt({'href': reverse('result_detail', kwargs={'result_id': self.pk})}), str(getattr(self, label))))


    @classmethod
    def update_search_vector(self):
        Result.objects.update(
            search_vector= (SearchVector('source', weight='A') +
                            SearchVector('type', weight='B') +
                            SearchVector('uuid', weight='C'))
        )

# This allows the users to define a process as they wish
# Could be split into "wet-lab process" and "computational process"
# or alternatively, "amplicon", "metagenomics", "metabolomics", "physical chemistry", etc.
class Category(models.Model):
    #This tracks which model this category associates with
    category_of = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField()
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'category_of'], name='Only one category of each name per model')
            ]
    def __str__(self):
        return self.name
 
### Key-Value storage for objects

class Value(models.Model):
    PARAMETER = 'parameter'
    METADATA = 'metadata'
    MEASURE = 'measure'
    VALUE_TYPES = (
            (PARAMETER, 'Parameter'),
            (METADATA, 'Metadata'),
            (MEASURE, 'Measure'))
    name = models.CharField(max_length=512)
    value_type = models.CharField(max_length=9, choices=VALUE_TYPES)
    # This generic relation links to a polymorphic Val class
    # Allowing Value to be str, int, float, datetime, etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    search_vector = SearchVectorField(null=True)

    def __str__(self):
        return self.name + ": " + str(self.content_object.value)

    @classmethod
    def update_search_vector(self):
        Value.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('content_object__value', weight='B') +
                            SearchVector('value_type', weight='C'))
        )


class StrVal(models.Model):
    value = models.TextField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="str")

class IntVal(models.Model):
    value = models.IntegerField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="int")

class FloatVal(models.Model):
    value = models.FloatField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="float")

class DatetimeVal(models.Model):
    value = models.DateTimeField()
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="date")

#This is if the input parameter is another result, ie. another artifact searched by UUID
class ResultVal(models.Model):
    value = models.ForeignKey('Result', on_delete=models.CASCADE)
    val_obj = GenericRelation(Value, object_id_field="object_id", related_query_name="result")
    def __str__(self):
        return value.name + ": " + value.type



class UserProfile(models.Model):
    #userprofile doesnt have a search vector bc it shouldn tbe searched.
    user = models.ForeignKey(User, on_delete=models.CASCADE, unique=True)

    @classmethod
    def create(cls, user):
        userprofile = cls(user=user)
        return userprofile
    def __str__(self):
        return self.user.email

class UploadInputFile(models.Model):
    STATUS_CHOICES = (
        ('P', "Processing"),
        ('S', "Success"),
        ('E', "Error")
    )
    userprofile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name='Uploader')
    upload_file = models.FileField(upload_to="upload/")
    upload_status = models.CharField(max_length=1, choices=STATUS_CHOICES)

    #Should upload files be indexed by the search??
    #search_vector = SearchVectorField(null=True)

    def __str__(self):
        return "UserProfile: {0}, UploadFile: {1}".format(self.userprofile, self.upload_file)

    def save(self, *args, **kwargs):
        self.upload_status = 'P'
        super().save(*args, **kwargs)
        #Call to celery, without importing from tasks.py (avoids circular import)
        current_app.send_task('db.tasks.react_to_file', (self.pk,))
        #output = result.collect()
        ##    print(i)
    def update(self, *args, **kwargs):
        super().save(*args, **kwargs)
        #return reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': self.pk})

class ErrorMessage(models.Model):
    """
    Store error messages for file uploads.
    """
    uploadinputfile = models.ForeignKey(UploadInputFile, on_delete=models.CASCADE, verbose_name='Uploaded File')
    error_message = models.CharField(max_length = 1000, null=True) #???? Maybe store as a textfile????


##Function for search.
##Search returns a list of dicts. Get the models from the dicts.
def load_mixed_objects(dicts,model_keys):
    #dicts are expected to have 'pk', 'rank', 'type'
    to_fetch = {}
    for d in dicts:
        to_fetch.setdefault(d['otype'], set()).add(d['pk'])
    fetched = {}

    for key, model, ui_string in model_keys:
        #disregard the ui_string variable. It's for frontend convenience.
        ids = to_fetch.get(key) or []
        objects = model.objects.filter(pk__in=ids)
        for obj in objects:
            fetched[(key, obj.pk)] = obj
    #return the list in the same otder as dicts arg
    to_return = []
    for d in dicts:
        item = fetched.get((d['otype'], d['pk'])) or None
        if item:
                item.original_dict = d
        to_return.append(item)

    return to_return
