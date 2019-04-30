####
#
#  The purpose of these functions is to clean and validate
#  input files for import into the Django models
#
####
import io
import zipfile
import uuid

import pandas as pd
import numpy as np

# import q2_extractor as q2e

def guess_filetype(unknown_file):
    #File types accepted: Sample Metadata (csv), Replicate Metadata (csv),
    # Protocol Data (csv), Protocol Deviation (csv),
    # artifact file (qza), visualization file (qzv)
    if zipfile.is_zipfile(unknown_file):
        #Probably an artifact/visualization file
        #check if the base directory is a uuid
        zf = zipfile.ZipFile(file_data)
        for filename in zf.namelist():
            try:
                uuid.UUID(filename.split("/")[0])
            except:
                raise ValueError("Not a valid QIIME QZA or QZV file. " \
                                 "All base directories must be a UUID.")
        return "qz"
    else:
        try:
            unknown_file.seek(0)
            table = parse_csv_or_tsv(unknown_file)
        except:
            raise
        #Sample Metadata only has sample-id required
        #Replicate Metadata has sample-id and replicate-id
        #Protocol Data has step, method, parameter_name, parameter_value, 
        # and description
        #Protocol Deviation has procotol_name, replicate-id, parameter_name, 
        # parameter_value
        if np.all([x in table for x in ["sample-id", "replicate-id", 
                                        "protocol"]]):
            return 'replicate_table'
        elif np.all([x in table for x in ["protocol_name", "replicate-id",
                                          "parameter_name", "parameter_value"]]):
            return 'protocoldeviation_table'
        elif np.all([x in table for x in ['step', 'method', 'parameter_name',
                                          'parameter_default', 'description']]):
            return 'protocol_table'
        elif 'sample-id' in table:
            return 'sample_table'
        else:
            raise ValueError("Could not parse input file.")



    

def parse_csv_or_tsv(table_file):
    table_string = table_file.read().decode()
    ctable=None
    ttable=None
    try:
        ctable = pd.read_table(io.StringIO(table_string), sep=",")
    except:
        pass
    try:
        ttable = pd.read_table(io.StringIO(table_string), sep="\t")
    except:
        pass
    if (ctable is None) & (ttable is None):
        raise ValueError("Could not parse as a CSV or TSV.")    
    if (ctable is not None) & (ttable is not None):
        if ctable.shape[1] > ttable.shape[1]:
            table = ctable
        else:
            table = ttable
    elif ctable:
        table = ctable
    else:
        table = ttable
    return table


def format_sample_metadata(metadata_file):
    #Take in a simple metadata spreadsheet, and return
    #a sample_id, metadata_name, metadata_value triplet
    #table
    #Note: This could work for both the SampleMetadata and
    #BiologicalReplicateMetadata
    table = parse_csv_or_tsv(metadata_file)
    if "sample-id" not in table:
        raise IndexError("sample-id not found in spreadsheet, this field is" \
                         "required.")
    mtable = pd.melt(table, id_vars=['sample-id'], 
                     var_name="key", value_name="value")
    return mtable


def format_protocol_sheet(protocol_file):
    #Take in a protocol sheet and return the step names, 
    #methods, descriptions for the ProtocolStep models
    #and the parameter defaults for the 
    #ProtocolStepParameters models
    #Will return two tables, as a result
    table = parse_csv_or_tsv(protocol_file)
    if not np.all([x in table for x in ["step", "method", 
                                       "parameter_name", "parameter_default", 
                                       "description"]]):
        raise IndexError("Missing column, required: step, method, " \
                  "parameter_name, parameter_default, description.")
    else:
        protocol_step_table = table[['step', 'method']].drop_duplicates()
        protocol_step_param_table = table[['step', 'method', 'description',
                                           'parameter_name', 
                                           'parameter_default']]
    return (protocol_step_table, protocol_step_param_table)
        
                                      

def format_artifact(artifact_file):
    #Using q2_extractor, rip the useful bits
    #out of a QIIME artifact and format it for
    #the models
    pass

