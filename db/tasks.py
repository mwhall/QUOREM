#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process
from __future__ import absolute_import, unicode_literals
import zipfile
from django.template import loader
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
            print("processing qiime file...")
            status = process_qiime_artifact(infile, upfile)
            print(status)
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

@shared_task
def process_qiime_artifact(infile, upfile):
    ## TODO: Integrate Q2 extractor for pipeline info etc.
    return "Nothing happened but all the stubs were called correctly."
    """
        A note on the below code:
        This is some basic, valid code which converts any uploaded QIIME
        artifact into a a zipfile containing the artifact as well as a template
        generated text file. This could be used to generate shell scripts that
        correspond to the qiime artifact.

   ###############################################
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
        return e """

@shared_task
def report_success(upfile):
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
