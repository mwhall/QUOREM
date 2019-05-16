#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process

from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.db import models
from django.apps import apps
from .formatters import guess_filetype, parse_csv_or_tsv
from django.core import serializers
from pprint import pprint
from .parser import Upload_Handler



@shared_task
def test_task(x):
    import os
    print(os.getppid())
    print("I'm a celery task!")

@shared_task
def nothing_task(ser_model):
    #just a test to try deserializing a django model objects
    for obj in serializers.deserialize("json", ser_model):
        print("sanity check")
        print(obj)
        obj.save()
        print("saved the object.")

@shared_task
def react_to_file(upload_file_id):
    ############################################################################
    #This is annoying but works for now
    UploadInputFile = apps.get_model('db.UploadInputFile')
    Investigation = apps.get_model('db.Investigation')
    Sample = apps.get_model('db.Sample')
    BiologicalReplicate = apps.get_model('db.BiologicalReplicate')
    SampleMetadata = apps.get_model('db.SampleMetadata')
    BiologicalReplicateMetadata = apps.get_model('db.BiologicalReplicateMetadata')
    BiologicalReplicateProtocol = apps.get_model('db.BiologicalReplicateProtocol')
    ############################################################################

    upfile = UploadInputFile.objects.get(id=upload_file_id)

    file_from_upload = upfile.upload_file._get_file()
    infile = file_from_upload.open()
    filetype = guess_filetype(infile)
    infile.seek(0)

    if filetype == 'qz':
        #Not sure what to do with a QIIME file at this point actually...
        print("QIIME artifact")
    if filetype == 'replicate_table':
        #Launch methods to parse the replicate table and create correspondig models.
        print("Replicate table...creating stuff!")
        uploadHandler = Upload_Handler()
        mapping_dict = {}
        with open("tests/data/labels.txt", "r") as file:
            mapping_dict = eval(file.read())
        data = parse_csv_or_tsv(infile)
        invs_from_file = uploadHandler.get_models(data, mapping_dict)
        print(invs_from_file)
        create_models_from_investigation_dict(invs_from_file)
        print("WOOHOO")
    if filetype == 'protocol_table':
        #launch methods to parse and save protocol data
        print("Protocol table. Yup")
        step_table, param_table = format_protocol_sheet(infile)
        print(step_table.to_string)
        print(param_table.to_string)

@shared_task
def create_models_from_investigation_dict(invs):
    #UGHHHHH
    ############################################################################
    #This is annoying but works for now
    UploadInputFile = apps.get_model('db.UploadInputFile')
    Investigation = apps.get_model('db.Investigation')
    Sample = apps.get_model('db.Sample')
    BiologicalReplicate = apps.get_model('db.BiologicalReplicate')
    SampleMetadata = apps.get_model('db.SampleMetadata')
    BiologicalReplicateMetadata = apps.get_model('db.BiologicalReplicateMetadata')
    BiologicalReplicateProtocol = apps.get_model('db.BiologicalReplicateProtocol')
    ############################################################################


    #iter investigations. an Investigation object 'has' Samples.
    for i in invs.keys():
        inv_num = invs[i].name
        #Check in the DB if the investigation exists.
        try:
            #get throws a DoesNotExist exception.
            inves = Investigation.objects.get(name=inv_num)
        except:
            #DNE. Create a new investigation
            #TODO populate the other investigation fields from file
            inves = Investigation(name=inv_num)
            inves.save()
        #iter samples. Sample objects 'have' replicates and metadata.
        for j in invs[i].samples.keys():
            sample_name = invs[i].samples[j].name
            try:
                samp = Sample.objects.get(investigation=inves.pk, name=sample_name)
            except:
                samp = Sample(investigation=inves, name=sample_name)
                samp.save()
            #iter sample metadata
            for k in invs[i].samples[j].metadata.keys():
                #no need to check for existing metadata, as far as I can tell.
                s_metadata = SampleMetadata(sample=samp, key=k, value=invs[i].samples[j].metadata[k])
                s_metadata.save()
            #iter biological replicates
            for k in invs[i].samples[j].biol_reps.keys():
                #Query for protocol, which is FK
                try:
                    #TODO get the protocol. for now just use pcr
                    protocol = BiologicalReplicateProtocol.objects.get(name="PCR")
                except:
                    protocol = BiologicalReplicateProtocol(name="PCR")
                    protocol.save()
                    print("protocol save worked")
                #Query for replicate.
                rep_name = invs[i].samples[j].biol_reps[k].name
                try:
                    rep = BiologicalReplicate.objects.get(name=rep_name)
                except:
                    rep = BiologicalReplicate(biological_replicate_protocol=protocol,
                                                investigation=inves,
                                                sample=samp, name=rep_name)
                    rep.save()
                #Save the replicate metdata.
                for l in invs[i].samples[j].biol_reps[k].metadata.keys():
                    r_metadata = BiologicalReplicateMetadata(biological_replicate=rep,
                                                            key=l, value=invs[i].samples[j].biol_reps[k].metadata[l])
