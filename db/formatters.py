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

from q2_extractor.Extractor import Extractor

class TableParser(object):
    def __init__(self, table_file):
        self.table = parse_csv_or_tsv(table_file)

    def initialize(self, object_name):
        dd = defaultdict(list)
        data = self.table[[x for x in self.table.columns if x.startswith(object_name) and (x.split(".")[0] in required_fields())]]
        data = data.melt().dropna().drop_duplicates().to_records(index=False)
        for field, datum in data:
            if datum not in dd[field.split(".")[0]]:
                dd[field.split(".")[0]].append(datum)
        return dd

    def initialize_generator(self):
        # Grabs the data necessary for Object.initialize(data)
        # Sorts it into objects so they can be initialized in dependency order
        for Obj in object_list:
            data = self.initialize(Obj.base_name)
            if data:
                yield (Obj, data)

    def update(self, object_name):
        # Retain ID fields from all objects in case they are needed to be passed
        # on for proxies
        table = self.table[[x for x in self.table.columns if (x.startswith(object_name)) or (x.split(".")[0] in id_fields())]]
        if table.empty:
            return {}
        table = table.drop_duplicates()
        for index, series in table.iterrows():
            series = series.dropna()
            if (object_name + "_id" not in series.index) and (object_name + "_name" not in series.index) and (object_name + "_uuid" not in series.index):
                continue
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
        value_targets = self.table[self.table.columns[self.table.columns.str.startswith("value_target")]].drop_duplicates().values.flatten()
        table = self.table[[x for x in self.table.columns if ((x.split("_")[0] in value_targets) and (x.split(".")[0] in id_fields())) or (x.split(".")[0] not in all_fields())]]
        table = table.melt(var_name="value_name", 
                           id_vars=[y for y in table.columns if (y.split(".")[0] in id_fields()) or (y == "value_type") or (y.startswith("value_target"))])
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

class ArtifactParser(TableParser):
    def __init__(self, artifact_path_or_file, provenance=True):
        self.extractor = Extractor(artifact_path_or_file)
        self.result_table = self.extractor.get_result(upstream=provenance)
        self.val_table = self.extractor.get_values()

    def initialize(self, object_name):
        dd = defaultdict(list)
        for table in [self.result_table, self.val_table]:
            data = table[[x for x in table.columns if x.startswith(object_name) and (x.split(".")[0] in required_fields())]]
            data = data.melt().dropna().drop_duplicates().to_records(index=False)
            for field, datum in data:
                if datum not in dd[field.split(".")[0]]:
                    dd[field.split(".")[0]].append(datum)
        return dd

    def update(self, object_name):
        # Retain ID fields from all objects in case they are needed to be passed
        # on for proxies
        table = self.result_table[[x for x in self.result_table.columns if (x.startswith(object_name)) or (x.split(".")[0] in id_fields())]]
        if table.empty:
            return {}
        table = table.drop_duplicates()
        for index, series in table.iterrows():
            series = series.dropna()
            if (object_name + "_id" not in series.index) and (object_name + "_name" not in series.index) and (object_name + "_uuid" not in series.index):
                continue
            dd = defaultdict(list)
            for _id in series.index:
                dd[_id.split(".")[0]].append(series[_id])
            if dd:
                yield dd

    def value_table(self):
        out_table = pd.DataFrame({})
        for table in [self.result_table, self.val_table]:
            value_targets = table[table.columns[table.columns.str.startswith("value_target")]].drop_duplicates().values.flatten()
            if len(value_targets) == 0:
                continue
            sub_table = table[[x for x in table.columns if ((x.split("_")[0] in value_targets) and (x.split(".")[0] in id_fields())) or (x.split(".")[0] not in all_fields())]]
            sub_table = sub_table.melt(var_name="value_name", 
                                  id_vars=[y for y in sub_table.columns if (y.split(".")[0] in id_fields()) or (y == "value_type") or (y.startswith("value_target"))])
            sub_table = sub_table.dropna(subset=["value"]).drop_duplicates()
            out_table = out_table.append(sub_table, ignore_index=True)
        return out_table

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
    table_string = table_file.read()
    if hasattr(table_string, "decode"):
        table_string = table_string.decode()
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

    if "result_uuid" in table:
        if pd.isna(table["result_uuid"]).all():
            # Then we need to generate a UUID for the entire sheet, which is used across entries
            # i.e., if you leave a totally blank result_id column, we'll make one for you (but only one)
            table.loc[:, "result_uuid"] = str(uuid.uuid1())
        else:
            #TODO: We need to go through and replace the levels with randomly generated UUIDs for each level
            pass

    return table
