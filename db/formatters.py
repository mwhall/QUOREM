####
#
#  The purpose of these functions is to clean and validate
#  input files for import into the Django models
#
####
from collections import defaultdict


from .models.object import Object
from .models import *

import io
import zipfile
import uuid

import pandas as pd
import numpy as np


#TODO Remove deprecated code.
#TODO add NaN cleaning to simple parser
def simple_sample_metadata_parser(table_file, overwrite):
    dataframe = parse_csv_or_tsv(table_file)
    try:
        assert dataframe.columns[0] in ['sample_name', 'sampleID', 'sample_id', 'sample']
    except:
        print("Format error: Simple parser accepts only sample metadata. First column must be one of 'sample_name', 'sample_id', 'sampleID', or 'sample'")
        return None, None

    #keep a list of not found samples.
    success = []
    not_found = []

    name_column = dataframe.columns[0]
    data_columns = [col for col in dataframe.columns if col != name_column]


    formatted_data = []
    for _, datum in dataframe.iterrows():
        as_kv = {}
        for i, val in enumerate(datum[data_columns]):
            as_kv[data_columns[i]] = val
        #list of (sample_name, {key:value}) tuples
        formatted_data.append( (datum[name_column], as_kv) )

    #iter formatted data. ONLY UPDATE SAMPLES, dont create any!
    for pair in formatted_data:
        try:
            sample = Sample.objects.get(name=pair[0])
        #pass if sample doesnt exist.
        except:
            not_found.append(pair[0])
            continue

        #create data.
        #print("OVERWRITE")
        #print(overwrite)
        for k, v in pair[1].items():
            dtype = Data.infer_type(v).type_name
            valtype = Value
            valdict = {'value_type': value.Value,
                       'name': k,
                       'data': v,
                       'data_type': dtype,
                       'samples': Sample.objects.filter(name=sample.name)}

            valqs = Value.get(**valdict)
            data = [v.data.get().value for v in valqs]
            if valdict['data'] in data:
                print("Already exists exactly")
                continue
            else:
                samplevals = sample.values.filter(signature__name=valdict['name'])
                if overwrite or len(samplevals) == 0:
                    for v in samplevals:
                        v.delete()
                    val = Value.create(**valdict)
                    sample.save()
    #return success and failure for user mail
    return success, not_found

#expects columns like object.field; e.g. sample.name
class TableParser(Object):
    def __init__(self, table_file):
        self.table = parse_csv_or_tsv(table_file)

    def initialize(self, object_name, Klass):
        dd = defaultdict(list)
        data = self.table[[x for x in self.table.columns if x.startswith(object_name) and (x.split(".")[1] in required_fields(Klass))]]
        data = data.melt().dropna().drop_duplicates().to_records(index=False)
        for field, datum in data:
            if datum not in dd[field.split(".")[0]]:
                dd[field.split(".")[0]].append(datum)
        return dd

    def initialize_generator(self):
        # Grabs the data necessary for Object.initialize(data)
        # Sorts it into objects so they can be initialized in dependency order
        for Obj in Object.get_object_types():
            data = self.initialize(Obj.base_name, Obj)
            if data:
                yield (Obj, data)

    def update(self, object_name, Klass):
        # Retain ID fields from all objects in case they are needed to be passed
        # on for proxies
        table = self.table[[x for x in self.table.columns if (x.startswith(object_name)) or (x.split(".")[0] in Klass.id_fields())]]
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
        for Obj in Object.get_object_types():
            for data in self.update(Obj.base_name, Obj):
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
