from django.db import models
from django.contrib.auth import get_user_model
from django.shortcuts import redirect

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
        sv =( SearchVector('name', weight='A') +
             SearchVector('description', weight='B') +
             SearchVector('institution', weight='C') )
        super().save(*args, **kwargs)
        Investigation.objects.update(search_vector = sv)
        refresh_automated_report("investigation")
        refresh_automated_report("investigation", pk=self.pk)


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


class Sample(models.Model):
    """
    Uniquely identify a single sample (i.e., a physical sample taken at some single time and place)
    """
    name = models.CharField(max_length=255,unique=True)
    investigation = models.ForeignKey('Investigation', on_delete=models.CASCADE)  # fk 2

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Sample.objects.update(
            search_vector = (SearchVector('name', weight= 'A') #+
                             # Should be investigation name, not pk.
                             # SearchVector('investigation', weight = 'B')
                             )
        )
        refresh_automated_report("sample", pk=self.pk)

class SampleMetadata(models.Model):
    """
    Stores arbitrary metadata in key-value pairs
    """
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    sample = models.ForeignKey('Sample', on_delete=models.CASCADE)  # fk 3

    search_vector = SearchVectorField(null=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sample', 'key'], name='One entry per sample-metadata key pair')
            ]
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        SampleMetadata.objects.update(
            search_vector = (SearchVector('key', weight='A') +
                              SearchVector('value', weight='B'))
        )

class BiologicalReplicate(models.Model):
    """
    A sample resulting from a biological analysis of a collected sample.
    If a poo sample is a sample, the DNA extracted and amplified with primer
    set A is a BiologicalReplicate of that sample
    """
    name = models.CharField(max_length=255,unique=True)
    sample = models.ForeignKey('Sample', on_delete=models.CASCADE, related_name='sample')  # fk 1
    #sequence_file = models.ManyToManyField('Document') # store the location of the sequence file(s)
    biological_replicate_protocol = models.ForeignKey('BiologicalReplicateProtocol', on_delete=models.CASCADE)  # fk 5
    #Should be locked down to match sample's Investigation field, but I can't
    #Ok, let's try the simple approach, where we fetch it through .sample.invesigation whenever we have a replicate
    #investigation = sample.investigation

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        BiologicalReplicate.objects.update(
            search_vector = (SearchVector('name', weight='A') #+
                            #  SearchVector('sample', weight='B') +
                            # SearchVector should use the sample NAME, not id. will need to query it....
                            # SearchVector('biological_replicate_protocol', weight='D') #+
                              #SearchVector('investigation', weight='C')
                              )
        )
class BiologicalReplicateMetadata(models.Model):
    """
    Metadata for the biological sample (PCR primers, replicate #, storage method, etc.)
    Basically anything that could change between a Sample and a BiologicalReplicate
    goes in here
    """
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE) # fk 14

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        BiologicalReplicateMetadata.objects.update(
            search_vector = (SearchVector('key', weight='A') +
                              SearchVector('value', weight='B')#+
                             # SearchVector('BiologicalReplicate', weight='C')
                             )
        )

#UNUSED, tagged for removal
class Document(models.Model):  #file
    """
    Store information to locate arbitrary files
    """
    md5_hash = models.CharField(max_length=255)
    document = models.FileField()
    #We can get size and location through the FileSystem manager in Django


class ProtocolParameterDeviation(models.Model):
    """
    Keep track of when a BiologicalReplicate isn't done exactly as SOP
    """
    # Identifies which replicate is deviating
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE)  # fk 9
    # Stores the default
    protocol_step = models.ForeignKey('ProtocolStep', on_delete=models.CASCADE) # fk ??
    # Comment expanding on what the deviation was
    description = models.TextField()
    # Stores the deviation from the default
    value = models.TextField()


class BiologicalReplicateProtocol(models.Model):
    """
    A list of the steps that the biological sample was processed with
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    citation = models.TextField() # should we include citations, or just have that in description?

    search_vector = SearchVectorField(null=True)
    def __str__(self):
        return "%s (%s)" % (self.name, self.citation)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        BiologicalReplicateProtocol.objects.update(
            search_vector = (SearchVector('name', weight='A') +
                             SearchVector('citation', weight='B') +
                             SearchVector('description', weight='C'))
        )
class ProtocolStep(models.Model):
    """
    Names and descriptions of the protocol steps and methods, e.g., stepname = 'amplification', method='pcr'
    """
    biological_replicate_protocols = models.ManyToManyField('BiologicalReplicateProtocol', related_name="steps")
    name = models.CharField(max_length=255)
    method = models.CharField(max_length=255)
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
        ProtocolStep.objects.update(
            search_vector= (SearchVector('name', weight='A') +
                            SearchVector('method', weight='B'))
        )

class ProtocolStepParameter(models.Model):
    """
    The default parameters for each protocol step
    """
    protocol_step = models.ForeignKey('ProtocolStep',
                                             on_delete=models.CASCADE, verbose_name="Protocol Step")
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    search_vector = SearchVectorField(null=True)
    class Meta:
        constraints = [
                models.UniqueConstraint(fields=['protocol_step', 'name'],
                    name='One entry per protocol step, parameter name pair')
            ]
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ProtocolStepParameter.objects.update(
            search_vector = (SearchVector('name', weight='A') +
                              SearchVector('description', weight='B') +
                              SearchVector('value', weight='C'))
        )

class ProtocolStepParameterDeviation(models.Model):
    """
    The deviations from the defaults, attached to a specific Replicate
    """
    protocol_step_parameter = models.ForeignKey('ProtocolStepParameter', on_delete=models.CASCADE)
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE)
    new_value = models.CharField(max_length=255)
    comment = models.TextField(blank=True)
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ProtocolStepParameterDeviation.objects.update(
            search_vector = (SearchVector('protocol_step_parameter', weight='A')+
                             SearchVector('new_value', weight='B')+
                             SearchVector('comment', weight='C'))
        )
class PipelineResult(models.Model):
    """
    Some kind of result from a ComputationalPipeline
    """
    list_display = ('source_software', 'result_type', 'replicates', 'pipeline_step')
    input_file = models.ForeignKey('UploadInputFile', on_delete=models.CASCADE, verbose_name="Result File Name")
    source_software = models.CharField(max_length=255, verbose_name="Source Software")
    result_type = models.CharField(max_length=255, verbose_name="Result Type")
    computational_pipelines = models.ManyToManyField('ComputationalPipeline', related_name='pipelines', verbose_name="Pipelines")
    # This pipeline result is
    pipeline_step = models.ForeignKey('PipelineStep', on_delete=models.CASCADE, verbose_name="Pipeline Step")
    replicates = models.ManyToManyField('BiologicalReplicate', related_name='replicates', verbose_name="Replicates")


class PipelineDeviation(models.Model):
    """
    Keep track of when an object's provenance involves deviations in the listed SOP
    """
    pipeline_result = models.ForeignKey('PipelineResult', on_delete=models.CASCADE)  # fk 11
    pipeline_parameter = models.ForeignKey('PipelineStepParameter', on_delete=models.CASCADE) # fk ??
    value = models.CharField(max_length=255)
    #TODO: Search Vectors that incorporate FK values.
    #Doing this directly will yield search results on the FK integer value, need
    #to implement queryset optimization to allow reference to FK model properties.


class ComputationalPipeline(models.Model):
    """
    Stores the steps and default parameters for a pipeline
    """
    name = models.CharField(max_length=255)
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ComputationalPipeline.objects.update(
            search_vector = (SearchVector('name', weight='A'))
        )


class PipelineStep(models.Model):
    """
    Describes a single step in the computational pipeline.
    These can be programatically defined by QIIME's transformations.
    """
    # many to many
    pipelines = models.ManyToManyField('ComputationalPipeline', related_name="steps")
    method = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    search_vector = SearchVectorField(null=True)
    def __str__(self):
        return '%s -> %s' % (self.method, self.action)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['method', 'action'], name='One entry per action-method pair')
            ]
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        PipelineStep.objects.update(
            search_vector = (SearchVector('method', weight='A') +
                             SearchVector('action', weight='B'))
        )

class PipelineStepParameter(models.Model):
    """
    The default parameters for each step, for this pipeline
    """
    pipeline_step = models.ForeignKey('PipelineStep', on_delete=models.CASCADE)  # fk 13
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    class Meta:
        constraints = [
                models.UniqueConstraint(fields=['pipeline_step', 'name'],
                    name='One entry per pipeline step, parameter name pair')
            ]



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
