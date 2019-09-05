from django.db import models
from django.contrib.auth import get_user_model

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.indexes import GinIndex

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
    name = models.CharField(max_length=255)
    sequence = models.TextField(null=True, blank=True)
    annotations = models.ManyToManyField('Value', related_name='annotations', blank=True)
    first_discovered_in = models.ForeignKey('Result', on_delete=models.CASCADE, blank=True)
    observed_results = models.ManyToManyField('Result', related_name='observed_results')
    observed_samples = models.ManyToManyField('Sample', related_name='observed_samples')

    values = models.ManyToManyField('Value', related_name="features", blank=True)
    categories = models.ManyToManyField('Category', related_name="features", blank=True)

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

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
    investigation = models.ForeignKey('Investigation', on_delete=models.CASCADE)  # fk 2
    process = models.ForeignKey('Process', on_delete=models.CASCADE, blank=True)

    upstream = models.ManyToManyField('self', related_name='downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="samples", blank=True)
    categories = models.ManyToManyField('Category', related_name='samples', blank=True)
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

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

    upstream = models.ManyToManyField('self', related_name="downstream", blank=True)

    parameters = models.ManyToManyField('Value', related_name="processes", blank=True)
    categories = models.ManyToManyField('Category', related_name="processes", blank=True)

    search_vector = SearchVectorField(null=True)
    def __str__(self):
        return "%s (%s)" % (self.name, self.citation)
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

    upstream = models.ManyToManyField('self', related_name='downstream', blank=True)

    parameters = models.ManyToManyField('Value', related_name='steps', blank=True)
    categories = models.ManyToManyField('Category', related_name='steps', blank=True)
    search_vector = SearchVectorField(null=True)
    def __str__(self):
        return '%s -> %s' % (self.name, self.method)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['name', 'method'], name='One entry per name-method pair')
            ]
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        Step.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('method', weight='B') +
                            SearchVector('description', weight='C'))
        )

class Analysis(models.Model):
    # This is an instantiation/run of a Process and its Steps
    name = models.CharField(max_length=255)
    date = models.DateTimeField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    process = models.ForeignKey('Process', on_delete=models.CASCADE)
    # Just in case this analysis had any extra steps, they can be defined and tagged here
    # outside of a Process
    extra_steps = models.ManyToManyField('Step')
    # Run-specific parameters can go in here, but I guess Measures can too
    values = models.ManyToManyField('Value', related_name='analyses')
    categories = models.ManyToManyField('Category', related_name='analyses', blank=True)
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

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
    source = models.CharField(max_length=255, verbose_name="Source Software/Instrument", blank=True)
    type = models.CharField(max_length=255, verbose_name="Result Type")
    analysis = models.ForeignKey('Analysis', on_delete=models.CASCADE)
    # This process result is from this step
    source_step = models.ForeignKey('Step', on_delete=models.CASCADE, verbose_name="Source Step")
    # Samples that this thing is the result for
    samples = models.ManyToManyField('Sample', related_name='results', verbose_name="Samples", blank=True)

    upstream = models.ManyToManyField('self', related_name='downstream', blank=True)

    values = models.ManyToManyField('Value', related_name="results", blank=True)
    categories = models.ManyToManyField('Category', related_name='results', blank=True)

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_search_vector(self):
        Result.objects.update(
            search_vector= (SearchVector('source_software', weight='A') +
                            SearchVector('result_type', weight='B') +
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

### Key-Value storage for objects

class Value(models.Model):
    PARAMETER = 'PA'
    METADATA = 'MD'
    MEASURE = 'ME'
    VALUE_TYPES = (
            (PARAMETER, 'Parameter'),
            (METADATA, 'Metadata'),
            (MEASURE, 'Measure'))
    name = models.CharField(max_length=512)
    value_type = models.CharField(max_length=2, choices=VALUE_TYPES)
    # This generic relation links to a polymorphic Val class
    # Allowing Value to be str, int, float, datetime, etc.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def __str__(self):
        return self.name + ": " + str(self.content_object.value)

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
        to_fetch.setdefault(d['type'], set()).add(d['pk'])
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
        item = fetched.get((d['type'], d['pk'])) or None
        if item:
                item.original_dict = d
        to_return.append(item)

    return to_return
