####
#
#  The purpose of these functions is to clean and validate
#  input files for import into the Django models
#
####
from collections import defaultdict

from .models import object_list, id_fields, required_fields, all_fields

import io
import zipfile
import uuid

import pandas as pd
import numpy as np

class TableParser(object):
    def __init__(self, table_file):
        self.table = parse_csv_or_tsv(table_file)

    def initialize(self, object_name):
        dd = defaultdict(list)
        data = self.table[[x for x in self.table.columns if x in required_fields() and x.startswith(object_name)]]
        data = data.melt().dropna().drop_duplicates().to_records(index=False)
        for field, datum in data:
            if datum not in dd[field]:
                dd[field].append(datum)
        return dd

    def initialize_generator(self):
        # Grabs the data necessary for Object.initialize(data)
        # Sorts it into objects so they can be initialized in dependency order
        for Obj in object_list:
            data = self.initialize(Obj.base_name)
            if data:
                yield (Obj, data)

    def update(self, object_name):
        table = self.table[[x for x in self.table.columns if x.startswith(object_name+"_")]]
        if table.empty:
            return {}
        table = table.drop_duplicates()
        for index, series in table.iterrows():
            series = series.dropna()
            dd = defaultdict(list)
            for _id in series.index:
                dd[_id.split(".")[0]].append(series[_id])
            if dd:
                yield dd

    def update_generator(self):
        for Obj in object_list:
            for data in self.update(Obj.base_name):
                yield (Obj, data)

    def value_table(self):
        table = self.table[[x for x in self.table.columns if (x in id_fields()) or (x.split(".")[0] not in all_fields())]]
        table = table.melt(var_name="value_name", 
                           id_vars=[y for y in table.columns if (y in id_fields()) or (y == "value_type") or (y.startswith("value_target"))])
        table = table.dropna(subset=["value"]).drop_duplicates()
        return table

    def iterrows(self):
        #Useful for feeding into Object.update(data)
        table = self.table[[x for x in all_fields() if x in self.table]].drop_duplicates()
        data = [ y[1].dropna().to_frame().to_records().tolist() for y in table.iterrows() ]
        for row in data:
            dd=defaultdict(list)
            for field, data in row:
                dd[field].append(data)
            yield dd


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
        ctable = pd.read_table(io.StringIO(table_string), sep=",", index_col=None, header=0 )
    except:
        pass
    try:
        ttable = pd.read_table(io.StringIO(table_string), sep="\t", index_col=None, header=0 )
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
#    table.columns = table.loc[0]
#    table = table.loc[1:]
    #And then squash any duplicate columns to the same name
    #NOTE: This means periods are FORBIDDEN?! I dunno how to feel about this atm. Better delimiter for q2_extractor?
#    table.columns = [x[0] for x in table.columns.str.split(".")]

    if "result_id" in table:
        if pd.isna(table["result_id"]).all():
            # Then we need to generate a UUID for the entire sheet, which is used across entries
            # i.e., if you leave a totally blank result_id column, we'll make one for you (but only one)
            table.loc[:, "result_id"] = str(uuid.uuid1())
        else:
            #TODO: We need to go through and replace the levels with randomly generated UUIDs for each level
            pass

    return table
