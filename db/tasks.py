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
BiologicalReplicate, BiologicalReplicateMetadata, BiologicalReplicateProtocol,
ErrorMessage, Investigation, Sample, SampleMetadata, UploadInputFile,
PipelineResult, PipelineStep, Measure, StrMeasure, FloatMeasure, IntMeasure, DatetimeMeasure,
ReplicateMeasure, FeatureMeasure, SampleMeasure, FeatureReplicateMeasure, InvestigationMeasure
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
    #Get BiologicalReplicates this file belongs to, based on file_table_str
    # Get PipelineStep this belongs to
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
            brep = BiologicalReplicate.objects.get(name__exact=replicate)
            pipelineresult.replicates.add(brep)
        except BiologicalReplicate.DoesNotExist:
            print("Replicate %s not found in database, link not made" % (replicate,))
        except Exception as e:
            print(e)
            raise Exception("Something else went wrong")
    print("right before scrape_measures")
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
    #   target: The object that this measure attached to, Investigation, Sample, BiologicalReplicate, Feature, FeatureReplicate,
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
            measurefunc = StrMeasure
        elif result_type == "Int":
            measurefunc = IntMeasure
        elif result_type == "Float":
            measurefunc = FloatMeasure
        elif result_type == "Datetime":
            measurefunc = DatetimeMeasure
        else:
            raise NotImplementedError("Unknown measure type %s" % (result_type,))
        measureval = measurefunc(value=value)
        measureval.save()
        measure = Measure(name=name, description=description,
                          pipeline_result=pipeline_result,
                          content_object=measureval)
        measure.save()
        if target == "BiologicalReplicate":
            breps = BiologicalReplicate.objects.filter(name__in=target_names)
            measure_wrapper = ReplicateMeasure
            mw = measure_wrapper(measure=measure)
            if len(breps) > 0:
                mw.replicates.add(breps)
            else:
                print("Warning: No matching replicates to add")
        elif target == "Sample":
            samples = Sample.objects.filter(name__in=target_names)
            measure_wrapper = SampleMeasure
            mw = measure_wrapper(measure=measure)
        elif target == "Feature":
            features = ",".join(target_names)
            measure_wrapper = FeatureMeasure
            mw = measure_wrapper(features=features, measure=measure)
        elif target == "Investigation":
            #Grab the replicates, then grab their investigation
            breps = BiologicalReplicate.objects.filter(name__in=q2e.get_replicates())
            #TODO: Allow it to at least catch if multiple
            if len(breps) > 0:
                investigation = breps[0].sample.investigation
            else:
                investigation = None
            measure_wrapper = InvestigationMeasure
            mw = measure_wrapper(measure=measure)
            if investigation is not None:
                mw.investigations.add(investigation)
        elif target == "FeatureReplicate":
            features = ",".join([x[0] for x in target_names])
            breps = BiologicalReplicate.objects.filter(name__in=[x[1] for x in target_names])
            measure_wrapper = FeatureReplicateMeasure
            mw = measure_wrapper(features=features, measure=measure)
            if len(breps) > 0:
                mw.replicates.add(breps)
            else:
                print("Warning: No matching replicates to add")
        else:
            raise NotImplementedError("Unknown measure target %s" % (target,))
        mw.save()


@shared_task
def report_success(upfile):
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    errorMessage = ErrorMessage(uploadinputfile=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
