#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process

from __future__ import absolute_import, unicode_literals
from celery import shared_task
from django.db import models
from django.apps import apps
from .formatters import guess_filetype, parse_csv_or_tsv
from .parser import resolve_input_row
from .models import BiologicalReplicate, BiologicalReplicateMetadata, \
                    BiologicalReplicateProtocol, ErrorMessage, Investigation, \
                    Sample, SampleMetadata, UploadInputFile

@shared_task
def react_to_file(upload_file_id):
    upfile = UploadInputFile.objects.get(id=upload_file_id)
    try:
        file_from_upload = upfile.upload_file._get_file()
        infile = file_from_upload.open()
        filetype = guess_filetype(infile)
        infile.seek(0)
        if filetype == 'qz':
            status = process_qiime_artifact(infile)
        elif filetype == 'table':
            status = process_table(infile)
        else:
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = ErrorMessage(uploadinputfile=upfile,
                                        error_message="Unidentified error with \
                                        filetype. Please contact Sys Admin.")
            errorMessage.save()
        if status == 'Success':
            report_success(upfile)
    except Exception as e:
        upfile.upload_status = 'E'
        upfile.update()
        errorMessage = ErrorMessage(uploadinputfile=upfile, error_message=e)
        errorMessage.save()

@shared_task
def process_table(infile):
    for index, row in parse_csv_or_tsv(infile).iterrows():
        try:
            print("Resolving row %d" % (index,))
            resolve_input_row(row)
            print("Resolved")
        except Exception as e:
            print(e)
    return "Success"

@shared_task
def report_success(upfile):
    #################################################################
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    ################################################################
    print("Success.")
    errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
