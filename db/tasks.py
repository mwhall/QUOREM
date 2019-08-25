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
from .models import (
Investigation, Sample, Replicate, Process, Step, Analysis,
Result, Value, StrVal, FloatVal, IntVal, DatetimeVal, ResultVal,
ErrorMessage, UploadInputFile
)

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
        status = ""
        if filetype == 'qz':
            print("processing qiime file...")
            try:
                status = process_qiime_artifact(infile, upfile)
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
            errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Upload failure.")
            errorMessage.save()
    except Exception as e:
        print("Except here")
        print(e)
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
    q2e = q2Extractor(infile)
    parameter_table_str, file_table_str = q2e.get_provenance()
    print("q2e get_provencance finished")
    #Validate the parameter_table, to check that all the steps are in the DB
    #If it matches perfectly to n, assign this artifact to those n pipelines
    #if it matches none, assign it to the closest one(s) and make a deviation
    source_software = "qiime2"
    result_type = q2e.type
    plugin = q2e.plugin
    action = q2e.action
    #Get Replicates this file belongs to, based on file_table_str
    # Get Step this belongs to
    try:
        step = Step.objects.get(**{"method__exact": plugin,
                                           "action__exact": action})
    except Step.DoesNotExist:
        step = Step(method=plugin, action=action)
        step.save()
    pipelineresult = Result(pipeline_step=step, input_file=upfile,
                                    source_software=source_software,
                                    result_type = result_type)
    pipelineresult.save()
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
            brep = Replicate.objects.get(name__exact=replicate)
            pipelineresult.replicates.add(brep)
        except Replicate.DoesNotExist:
            print("Replicate %s not found in database, link not made" % (replicate,))
        except Exception as e:
            print(e)
            raise Exception("Something else went wrong")
    provtab = pd.read_csv(io.StringIO(parameter_table_str), sep="\t")
    for item in provtab.index:
        step = Step.objects.filter(method__exact=item['pipeline_step_id'],
                                           action__exact=item['pipeline_step_action'])
        if len(step) == 0:
            step = Step(method=item['pipeline_step_id'],
                                action=item['pipeline_step_action'])
        else:
            #unique constraint, this should only be one thing
            step = step[0]

    scrape_measures(q2e, pipelineresult)
    return "Success"

@shared_task
def scrape_measures(q2e, pipeline_result):
    #Suck the goodies out of the artifacts that we know how to import
    result_type = q2e.type
    try:
        print("try block")
        data = q2e.extract_measures()
        print("q2e extract measures finished")
    except NotImplementedError:
        print("not implemented")
        raise NotImplementedError("q2_extractor does not know how to extract measures from this file")
    #Tuple description:
    #  (name: The name of the measure,
    #   description: A description of the measure,
    #   result_type: Basic type of measure, Str, Int, Float, or Datetime,
    #   value: The data payload,
    #   target: The object that this measure attached to, Investigation, Sample, Replicate, Feature, FeatureReplicate,
    #   target_names: An iterable containing the target names, unless it is FeatureReplicate in which case it is an iterable containing (feature, replicate) pairs
    #  )
    #TODO: Move to a separate function so others can call the measure saving software without
    #all of this q2e context
    print("after try/catch, befure iteration")
    for measure_tuple in data:
        name = measure_tuple[0]
        description = measure_tuple[1]
        result_type = measure_tuple[2]
        value = measure_tuple[3]
        target = measure_tuple[4]
        target_names = measure_tuple[5]
        if result_type == "Str":
            measurefunc = StrVal
        elif result_type == "Int":
            measurefunc = IntVal
        elif result_type == "Float":
            measurefunc = FloatVal
        elif result_type == "Datetime":
            measurefunc = DatetimeVal
        else:
            raise NotImplementedError("Unknown measure type %s" % (result_type,))

@shared_task
def report_success(upfile):
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    #update the search vectors
    model_list = [Investigation, Sample, Replicate, Process, Step, Analysis, Result, Value]
    for model in model_list:
        try:
            model.update_search_vector()
            print(model, " sv updated")
        except:
            continue
    errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
