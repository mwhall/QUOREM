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
from .formatters import guess_filetype, parse_csv_or_tsv
from .parser import resolve_input_row, resolve_table
from .models import (
Investigation, Sample, Feature, Process, Step, Analysis,
Result, Value, StrVal, FloatVal, IntVal, DatetimeVal, ResultVal,
UploadMessage, File, UserProfile, UserMail
)

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
        file_from_upload = upfile.upload_file._get_file()
        infile = file_from_upload.open()
#        filetype = guess_filetype(infile)
#        infile.seek(0)
#        print(filetype)
        status = ""
        if from_form == "A":
            mail.title="The qiime artifact you uploaded "
            print("Processing qiime file...")
            try:
                status = process_qiime_artifact(infile, upfile, analysis_pk=kwargs["analysis_pk"], register_provenance=kwargs["register_provenance"])
            except Exception as e:
                print(e)

        elif from_form == "S":
            mail.title="The spreadsheet you uploaded "
            print("Processing table ...")
            status = process_table_cache(infile)
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
def process_table_cache(infile):
    resolve_table(parse_csv_or_tsv(infile))
    return "Success"

@shared_task
def process_qiime_artifact(infile, upfile, analysis_pk, register_provenance):
    start_time = time.time()
    analysis_name = Analysis.objects.get(pk=analysis_pk).name
    q2e = Extractor(infile)
    uuid = q2e.base_uuid
    if register_provenance:
        result_table = q2e.get_result().reset_index()
    else:
        result_table = q2e.get_result(upstream=False).reset_index()
    #And then squash any duplicate columns to the same name
    #NOTE: This means periods are FORBIDDEN?! I dunno how to feel about this atm. Better delimiter for q2_extractor?
    result_table.columns = [x[0] for x in result_table.columns.str.split(".")]
    result_table["analysis_id"] = analysis_name
    if register_provenance:
        prov_str = "with"
    else:
        prov_str = "without"
    print("Resolving artifact %s provenance" % (prov_str,))
    resolve_table(result_table)
    #for index, row in result_table.iterrows():
    #    try:
    #        row["analysis_id"] = analysis_name
    #        resolve_input_row(row.dropna())
    #    except Exception as e:
    #        raise e
    print("Getting values")
    value_table = q2e.get_values()
    print("Got values")
    #And then squash any duplicate columns to the same name
    #NOTE: This means periods are FORBIDDEN?! I dunno how to feel about this atm. Better delimiter for q2_extractor?
    value_table.columns = [x[0] for x in value_table.columns.str.split(".")]
    value_table["analysis_id"] = analysis_name
    #for index, row in value_table.iterrows():
    #    try:
    #        row["analysis_id"] = analysis_name
    #        resolve_input_row(row.dropna())
    #    except Exception as e:
    #        raise e
    print("Resolving values")
    resolve_table(value_table)
    res = Result.objects.get(uuid=uuid)
    res.input_file = upfile
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
