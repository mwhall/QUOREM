#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process

from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.db import models
from django.apps import apps
from .formatters import guess_filetype, parse_csv_or_tsv
from .parser import Upload_Handler



@shared_task
def test_task(x):
    import os
    print(os.getppid())
    print("I'm a celery task!")


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
    ErrorMessage = apps.get_model('db.ErrorMessage')
    ############################################################################

    upfile = UploadInputFile.objects.get(id=upload_file_id)
    try:
        file_from_upload = upfile.upload_file._get_file()
        infile = file_from_upload.open()
        filetype = guess_filetype(infile)
        infile.seek(0)

        if filetype == 'qz':
        #Not sure what to do with a QIIME file at this point actually...
            print("QIIME artifact")
        #    return('qiime artifact, handling not yet configured')
        elif filetype == 'replicate_table':
        #Launch methods to parse the replicate table and create correspondig models.
            print("Replicate table...creating stuff!")
            uploadHandler = Upload_Handler()
            mapping_dict = {}
            with open("tests/data/labels.txt", "r") as file:
                mapping_dict = eval(file.read())
            data = parse_csv_or_tsv(infile)
            invs_from_file, new_invs, new_samples = uploadHandler.get_models(data, mapping_dict)
            create_models_from_investigation_dict(invs_from_file)
            upfile.upload_status = 'S'
            #update just calls super.save() because vanilla save() has been overridden
            #to trigger a file upload process.
            upfile.update()
            print("Success.")
            message = 'Uploaded Successfully.\n'
            if new_invs:
                message += "Created the following new Investigations: \n"
                for key in new_invs.keys():
                    message += key
                    message += "\n"
            if new_samples:
                message += "Created the following new Samples: \n"
                for key in new_samples.keys():
                    message += key
                    message += "\n"
            errorMessage = ErrorMessage(uploadinputfile=upfile, error_message=message)
            errorMessage.save()
        #    return('success')
        elif filetype == 'protocol_table':
        #launch methods to parse and save protocol data
            print("Protocol table. Yup")
            step_table, param_table = format_protocol_sheet(infile)
            print(step_table.to_string)
            print(param_table.to_string)
        #    return('protocol table, handling not yet configured')
        else:
            upfile.upload_status = 'E'
            upfile.update()
            print("ERROR WITH FILE TYPE")
            print("Fail- Upload Status changed to Error")
            errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Unidentified error with filetype. Please contact Sys Admin.")
            errorMessage.save()
        #    return('error')
    except Exception as e:
    ###############################################################
        upfile.upload_status = 'E'
        upfile.update()
        print("EXCEPTION")
        print(e)
        errorMessage = ErrorMessage(uploadinputfile=upfile, error_message=e)
        errorMessage.save()
        print("Fail- Upload Status changed to Error")
    #    return('error')
    ##############################################################

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
