from django.db import models
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from .formatters import guess_filetype, parse_csv_or_tsv, format_sample_metadata, format_protocol_sheet, format_artifact
import pandas as pd

User = get_user_model()

#We need to wrap the auth model to make it a model the djk will work with
#It must be based on models.Model, but User is based on AbstractUser
#But this allows us to store metadata
EXAMPLE_CHOICES = (
            ('1', 'First Choice'),
            ('2', 'Second Choice'),
)

#####################Just an exampe ##########################################
class ExampleModel(models.Model):
    name = models.CharField(max_length=100)
    selection = models.CharField(max_length=1, choices=EXAMPLE_CHOICES)
    def __str__(self):
        return self.name
###############################################################################
class UserProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    @classmethod
    def create(cls, user):
        userprofile = cls(user=user)
        return userprofile
    def __str__(self):
        return self.user.email

class UploadInputFile(models.Model):
    userprofile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name='Uploader')
    FILE_SELECTION = (
            ('Sample', 'Sample Data'),
            ('BiologicalProtocol', 'Protocol Spreadsheet'),
            ('SampleMetaData', 'Sample Metadata Spreadsheet'),
    )
    input_type = models.CharField(max_length=30, choices=FILE_SELECTION)
    upload_file = models.FileField(upload_to="upload/")
    file_type = models.CharField(max_length=255)
    file_size = models.FloatField()
 #  Mike had the below line, but it causes an error on my pc - Alex
#   UploadInputFile(userprofile, upload_file)
    def save(self, *args, **kwargs):
        #CHECK THAT ITS VALID HERE

        #Note: upload_file is now a Django object called FieldFile and has access to its methods
        # and attributes, many of which are useful.

        file_from_upload = self.upload_file._get_file()
        self.file_size = file_from_upload.size
        #file_from_upload is now Django File, which wraps a Python File
        infile = file_from_upload.open()
        filetype = guess_filetype(infile)
        self.file_type = filetype
        #Reset the file seeker to the start of the file so as to be able to read it again for processing
        infile.seek(0)
        react_to_filetype(filetype,infile)

        super().save(*args, **kwargs)
        #THIS IS WHERE THE FILE CAN BE VALIDATED
        print(self.upload_file)

#This method can 'do stuff' to the uploaded file.
def react_to_filetype(filetype, infile):
    if filetype == 'qz':
        #Not sure what to do with a QIIME file at this point actually...
        print("QIIME artifact")
    if filetype == 'replicate_table':
        #Launch methods to parse the replicate table and create correspondig models.
        print("Replicate table...creating stuff!")
    if filetype == 'protocol_table':
        #launch methods to parse and save protocol data
        print("Protocol table. Yup")
        step_table, param_table = format_protocol_sheet(infile)
        print(step_table.to_string)
        print(param_table.to_string)

class Investigation(models.Model):
    """
    Groups of samples, biosamples, and compsamples
    """
    name = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)
    description = models.TextField()
    def __str__(self):
        return self.name

class Sample(models.Model):
    """
    Uniquely identify a single sample (i.e., a physical sample taken at some single time and place)
    """
    name = models.CharField(max_length=255,unique=True)
    investigation = models.ForeignKey('Investigation', on_delete=models.CASCADE)  # fk 2
    def __str__(self):
        return self.name

class SampleMetadata(models.Model):
    """
    Stores arbitrary metadata in key-value pairs
    """
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    sample = models.ForeignKey('Sample', on_delete=models.CASCADE)  # fk 3

class BiologicalReplicate(models.Model):
    """
    A sample resulting from a biological analysis of a collected sample.
    If a poo sample is a sample, the DNA extracted and amplified with primer
    set A is a BiologicalReplicate of that sample
    """
    name = models.CharField(max_length=255,unique=True)
    sample = models.ForeignKey('Sample', on_delete=models.CASCADE, related_name='sample')  # fk 1
    sequence_file = models.ManyToManyField('Document') # store the location of the sequence file(s)
    biological_replicate_protocol = models.ForeignKey('BiologicalReplicateProtocol', on_delete=models.CASCADE)  # fk 5
    #Should be locked down to match sample's Investigation field, but I can't
    investigation = models.ForeignKey('Investigation', on_delete=models.CASCADE)

class BiologicalReplicateMetadata(models.Model):
    """
    Metadata for the biological sample (PCR primers, replicate #, storage method, etc.)
    Basically anything that could change between a Sample and a BiologicalReplicate
    goes in here
    """
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE) # fk 14


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
    name = models.CharField(max_length=255)
    description = models.TextField()
    citation = models.TextField() # should we include citations, or just have that in description?
#    protocol_steps = models.ManyToManyField('ProtocolStep')

class ProtocolStep(models.Model):
    """
    Names and descriptions of the protocol steps and methods, e.g., stepname = 'amplification', method='pcr'
    """
    biological_replicate_protocols = models.ManyToManyField('BiologicalReplicateProtocol', blank=True)
    name = models.CharField(max_length=255)
    method = models.CharField(max_length=255)
    def __str__(self):
        return '%s -> %s' % (self.name, self.method)

"""
def protocol_step_from_table(intable):
    count = 0
    pks = [] #keys of created protocols
    for index, row in intable.iterrows():
        #table should have columns 'step' and 'method'
        protocolStep = ProtocolStep(name=row['step'], method=row['method'])
        protocolStep.save()
        count += 1
    print("Added ", count, " entries to table ProtocolStep")
"""
class ProtocolStepParameter(models.Model):
    """
    The default parameters for each protocol step
    """
    protocol_step = models.ForeignKey('ProtocolStep',
                                             on_delete=models.CASCADE, verbose_name="Protocol Step") # fk ??
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)

#####TODO Ensure ProtocolStep and ProtocolStepParameter are made at the same time, share keys where needed
"""
def protocol_step_parameter_from_table(intable):
    count = 0

    for index, row in intable.iterrows():
        #table should have 'step', 'method', 'description', 'parameter_name', and 'parameter_default'
        protocolStepParameter = ProtocolStepParameter(protocol_step=fks[count], name='
"""

class ProtocolStepParameterDeviation(models.Model):
    """
    The deviations from the defaults, attached to a specific Replicate
    """
    protocol_step_parameter = models.ForeignKey('ProtocolStepParameter', on_delete=models.CASCADE)
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE)
    new_value = models.CharField(max_length=255)
    comment = models.TextField(blank=True)

class PipelineResult(models.Model):
    """
    Some kind of result from a ComputationalPipeline
    """
    document = models.ManyToManyField('Document')
    computational_pipeline = models.ForeignKey('ComputationalPipeline', on_delete=models.CASCADE)
    pipeline_step = models.ForeignKey('PipelineStep', on_delete=models.CASCADE)
    replicates = models.ManyToManyField('BiologicalReplicate')


class PipelineDeviation(models.Model):
    """
    Keep track of when an object's provenance involves deviations in the listed SOP
    """
    pipeline_result = models.ForeignKey('PipelineResult', on_delete=models.CASCADE)  # fk 11
    pipeline_parameter = models.ForeignKey('PipelineParameter', on_delete=models.CASCADE) # fk ??
    value = models.CharField(max_length=255)


class ComputationalPipeline(models.Model):
    """
    Stores the steps and default parameters for a pipeline
    """
    pipeline_step = models.ManyToManyField('PipelineStep') # fk 12


class PipelineStep(models.Model):
    """
    Describes a single step in the computational pipeline.
    These can be programatically defined by QIIME's transformations.
    """
    # many to many
    name = models.CharField(max_length=255)


class PipelineParameter(models.Model):
    """
    The default parameters for each step, for this pipeline
    """
    computational_pipeline = models.ForeignKey('ComputationalPipeline', on_delete=models.CASCADE) # fk ??
    pipeline_step = models.ForeignKey('PipelineStep', on_delete=models.CASCADE)  # fk 13
    value = models.CharField(max_length=255)
    key = models.CharField(max_length=255)
