#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process
from __future__ import absolute_import, unicode_literals
import zipfile
import time
from django.template import loader
from celery import shared_task
from django.db import models, transaction
from django.apps import apps

from .formatters import guess_filetype, parse_csv_or_tsv, TableParser, ArtifactParser
from .models import *

from q2_extractor.Extractor import Extractor
import pandas as pd
import io
import re
############### For Testing, delete later.
import time
#########################################
@shared_task
def react_to_file(upload_file_id, **kwargs):
    #something weird happens sometimes in which uploading a file doens't work.
    #it throws an ID not found error. Trying again and changing nothing seems to work
    #So, make it try twice, then throw an error if it still doesn't work.
    try:
        upfile = File.objects.get(id=upload_file_id)
    except:
        try:
        #rarely it doesn't work for no apparent reason. Sleep and try again.
            time.sleep(1)
            upfile = File.objects.get(id=upload_file_id)
        except Exception as e:
            print("error with upfile. Cannot find the file. Sys Admin should remove.")
            print(e)
    try:
        #user will recieve mail to let them know the atstus of their upload.
        mail = UserMail(user=upfile.userprofile)

        from_form = upfile.upload_type
        # S for Spreadsheet
        # A for Artifact
        status = ""
        if from_form == "A":
            mail.title="The qiime artifact you uploaded "
            print("Processing qiime file...")
            try:
                status = process_qiime_artifact(upfile, analysis_pk=kwargs["analysis_pk"], register_provenance=kwargs["register_provenance"])
            except Exception as e:
                print(e)

        elif from_form == "S":
            mail.title="The spreadsheet you uploaded "
            print("Processing table ...")
            status = process_table(upfile)
            print(status)
        else:
            mail.title="A rare error occurred with your upload."
            mail.message="The system was unable to recognize your upload file.\
                          Please double check your file selection. If this problem\
                          persists, please contact the devlopers of QUOR'em. "
            mail.save()
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = UploadMessage(file=upfile,
                                        error_message="Unidentified error with \
                                        filetype. Please contact Sys Admin.")
            errorMessage.save()
        if status == 'Success':
            mail.title += "was successfully added to QUOR'em."
            mail.message = "Your file upload completed successfully. You will now \
            be able to browse, visualize, and search for your data."
            mail.save()
            report_success(upfile)
        else:
            mail.title += "failed."
            mail.message = "Your file upload failed. Please try again."
            mail.save()
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = UploadMessage(file=upfile, error_message="Upload failure.")
            errorMessage.save()

    except Exception as e:
        mail.title += "failed."
        mail.message = "Your file upload failed. The system gave the following error: "
        mail.message += str(e)
        mail.message += " please try reformatting your data and reuploading."
        mail.save()
        print("Except here")
        print(e)
        upfile.upload_status = 'E'
        upfile.update()
        errorMessage = UploadMessage(file=upfile, error_message=e)
        errorMessage.save()

@shared_task
def process_table(upfile):
    infile = upfile.upload_file._get_file().open()
    print("Getting logger")
    lgr = upfile.logfile.get_logger()
    print("Getting parser")
    tp = TableParser(infile)
    print("Initializing")
    for model, data in tp.initialize_generator():
        print("For %s" % (model.base_name,))
        model.initialize(data, log=lgr)
    print("Updating")
    for model, data in tp.update_generator():
        model.update(data, log=lgr)
#    print("Adding values")
#    Value.add_values(tp.value_table(), log=lgr)
    return "Success"

@shared_task
def process_qiime_artifact(upfile, analysis_pk, register_provenance):
    infile = upfile.upload_file._get_file().open()
    print("Getting logger")
    lgr = upfile.logfile.get_logger()
    start_time = time.time()
    analysis_name = Analysis.objects.get(pk=analysis_pk).name
    ap = ArtifactParser(infile, provenance=register_provenance)
    result_uuid = ap.extractor.base_uuid
    for model, data in ap.initialize_generator():
        print("Initializing for %s" % (model.plural_name,))
        if not data:
            continue
        #Injnect the analysis name as an atomic list
        if model.base_name == "result":
            data["result_analysis"] = [analysis_name]
        model.initialize(data, log=lgr)
    print("Updating")
    for model, data in ap.update_generator():
        if not data:
            continue
        # Inject the analysis name as an atomic list
        if model.base_name == "result":
            data["result_analysis"] = [analysis_name]
        model.update(data, log=lgr)
    print("Adding and linking values")
    Value.add_values(ap.value_table(), log=lgr)
    res = Result.objects.get(uuid=result_uuid)
    res.file = upfile
    res.save()
    print("#\n#\n")
    print("~~~~~~~~~TOTAL TIME TO RUN ~~~~~~~~~~~\n#\n")
    print(time.time() - start_time)
    print("#\n#\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    return "Success"

@shared_task
def report_success(upfile):
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    #update the search vectors
    model_list = [Investigation, Sample, Feature, Process, Step, Analysis, Result, Value]
    for model in model_list:
        try:
            model.update_search_vector()
            print(model, " sv updated")
        except Exception as e:
            print(e)
            print(model, " sv didn't work")
            continue
    errorMessage = UploadMessage(file=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
