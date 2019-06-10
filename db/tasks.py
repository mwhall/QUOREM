#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process
from __future__ import absolute_import, unicode_literals
import zipfile
import time
from django.template import loader
from celery import shared_task
from django.db import models
from django.apps import apps
from .formatters import guess_filetype, parse_csv_or_tsv
from .parser import resolve_input_row
from .models import BiologicalReplicate, BiologicalReplicateMetadata, \
                    BiologicalReplicateProtocol, ErrorMessage, Investigation, \
                    Sample, SampleMetadata, UploadInputFile, PipelineResult, \
                    PipelineStep

from q2_extractor.Extractor import q2Extractor
import pandas as pd
import io
import re
@shared_task
def react_to_file(upload_file_id):
    #something weird happens sometimes in which uploading a file doens't work.
    #it throws an ID not found error. Trying again and changing nothing seems to work
    #So, make it try twice, then throw an error if it still doesn't work.
    try:
        upfile = UploadInputFile.objects.get(id=upload_file_id)
    except:
        try:
        #rarely it doesn't work for no apparent reason. Sleep and try again.
            time.sleep(1)
            upfile = UploadInputFile.objects.get(id=upload_file_id)
        except Exception as e:
            print("error with upfile. Cannot find the file. Sys Admin should remove.")
            print(e)
    try:
        file_from_upload = upfile.upload_file._get_file()
        infile = file_from_upload.open()
        filetype = guess_filetype(infile)
        infile.seek(0)
        print(filetype)

        if filetype == 'qz':
            print("processing qiime file...")
            try:
                status = process_qiime_artifact(infile, upfile)
                print(status)
            except Exception as e:
                print(e)

        elif filetype == 'table':
            print("processing table ...")
            status = process_table(infile)
            print(status)
        else:
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = ErrorMessage(uploadinputfile=upfile,
                                        error_message="Unidentified error with \
                                        filetype. Please contact Sys Admin.")
            errorMessage.save()
        if status == 'Success':
            report_success(upfile)
        else:
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = ErrorMessage(uploadinputfile=upfile, error_message=status)
            errorMessage.save()
    except Exception as e:
        upfile.upload_status = 'E'
        upfile.update()
        errorMessage = ErrorMessage(uploadinputfile=upfile, error_message=e)
        errorMessage.save()

@shared_task
def process_table(infile):
    #TODO instead of having it stop, let it process all rows
    #and return all errors from all bad rows
    for index, row in parse_csv_or_tsv(infile).iterrows():
        try:
            resolve_input_row(row)
        except Exception as e:
            print(e)
            raise e
    return "Success"

"""
try:
    #an artifact is either qzv or qza.
    name = upfile.upload_file.name
    zip_name = name[:-3] + "zip"
    zf = zipfile.ZipFile(zip_name, mode='a')
    zf.write(name)
    with open('filetext.txt', mode='w') as textfile:
        template = loader.get_template('db/test_template.txt')
        s = template.render({'passed_in':"GEORGE"})
        textfile.write(s)
    zf.write('filetext.txt')
    zf.close()
    upfile.upload_file = zf.filename
    upfile.update()
    print(upfile.upload_file.url)
    return 'Success'
except Exception as e:
    return e
"""

@shared_task
def process_qiime_artifact(infile, upfile):
    print("Extracting QIIME info")
    q2e = q2Extractor(infile)
    print("Getting provenance")
    parameter_table_str, file_table_str = q2e.get_provenance()

    #Validate the parameter_table, to check that all the steps are in the DB
    #If it matches perfectly to n, assign this artifact to those n pipelines
    #if it matches none, assign it to the closest one(s) and make a deviation
    source_software = "qiime2"
    result_type = q2e.type
    plugin = q2e.plugin
    action = q2e.action
    #Get BiologicalReplicates this file belongs to, based on file_table_str
    # Get PipelineStep this belongs to
    print("Matching with entries in database")
    try:
        step = PipelineStep.objects.get(**{"method__exact": plugin,
                                           "action__exact": action})
    except PipelineStep.DoesNotExist:
        step = PipelineStep(method=plugin, action=action)
        step.save()
    pipelineresult = PipelineResult(pipeline_step=step, input_file=upfile,
                                    source_software=source_software,
                                    result_type = result_type)
    pipelineresult.save()
    print("Saving PipelineResults as id %s" % (pipelineresult.id,))
    filetab = pd.read_csv(io.StringIO(file_table_str), sep="\t")
    replicates = set()
    for item in filetab.index:
        regex = re.compile("_S0_L001_R[12]_001.fastq.gz")
        fname = filetab.loc[item]['filename']
        if regex.search(fname) is not None:
            replicates.add(fname.split("_")[0])
    for replicate in replicates:
        #Search for sample in database
        try:
            #This should never return more than one, unique constraint
            print("Adding %s to PipelineResult" % (replicate,))
            brep = BiologicalReplicate.objects.get(name__exact=replicate)
            pipelineresult.replicates.add(brep)
            print("Added")
            print(pipelineresult.replicates.all())
        except BiologicalReplicate.DoesNotExist:
            print("Replicate %s not found in database, link not made" % (replicate,))
        except Exception as e:
            print(e)
            raise Exception("Something else went wrong")

@shared_task
def report_success(upfile):
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
