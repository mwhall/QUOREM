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

def guess_filetype(unknown_file):
    #File types accepted: Sample Metadata (csv), Replicate Metadata (csv),
    # Protocol Data (csv), Protocol Deviation (csv),
    # Pipeline Data (csv),
    # artifact file (qza), visualization file (qzv)
    if zipfile.is_zipfile(unknown_file):
        #Probably an artifact/visualization file
        #check if the base directory is a uuid
        zf = zipfile.ZipFile(unknown_file)
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
            return "table"
        except:
            raise
        raise ValueError("Could not guess input file type.")

def parse_csv_or_tsv(table_file):
    table_string = table_file.read().decode()
    ctable=None
    ttable=None
    try:
        ctable = pd.read_table(io.StringIO(table_string), sep=",", index_col=None, header=None )
    except:
        pass
    try:
        ttable = pd.read_table(io.StringIO(table_string), sep="\t", index_col=None, header=None )
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
    #This bit allows us to have duplicate columns, something we need here
    table.columns = table.loc[0]
    table = table.loc[1:]
    #And then squash any duplicate columns to the same name
    #NOTE: This means periods are FORBIDDEN?! I dunno how to feel about this atm. Better delimiter for q2_extractor?
    table.columns = [x[0] for x in table.columns.str.split(".")]

    if "result_id" in table:
        if pd.isna(table["result_id"]).all():
            # Then we need to generate a UUID for the entire sheet, which is used across entries
            # i.e., if you leave a totally blank result_id column, we'll make one for you (but only one)
            table.loc[:, "result_id"] = str(uuid.uuid1())
        else:
            #TODO: We need to go through and replace the levels with randomly generated UUIDs for each level
            pass

    return table
