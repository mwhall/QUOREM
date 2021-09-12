import zipfile
import yaml
import re
import os
import time
import tempfile
import h5py as h5
import ete3

from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.conf import settings

from celery import current_app
from scipy.sparse import coo_matrix, csr_matrix
import pandas as pd

from .models.object import Object
from .models.value import Value
from .models.sample import Sample
from .models.feature import Feature
from .models.step import Step
from .models.file import UploadFile

def scalar_constructor(loader, node):
    value = loader.construct_scalar(node)
    return value

yaml.add_constructor('!ref', scalar_constructor)
yaml.add_constructor('!no-provenance', scalar_constructor)
yaml.add_constructor('!color', scalar_constructor)
yaml.add_constructor('!cite', scalar_constructor)
yaml.add_constructor('!metadata', scalar_constructor)

def infer_spreadsheet_type(spreadsheet_file_or_path):
    if isinstance(spreadsheet_file_or_path, str):
        filename = spreadsheet_file_or_path
    elif type(spreadsheet_file_or_path) == UploadFile:
        filename = spreadsheet_file_or_path.name
    else:
        filename = spreadsheet_file_or_path.name
    #TODO: put a function in SDS to spit out the priority order of sheet types
    for sheet_type in SpreadsheetDataScraper.__subclasses__():
        try:
            print("Checking sheet type %s" % (sheet_type,))
            if sheet_type.compatible(filename):
                return sheet_type.sheet_format
        except:
            continue
    return None

def ingest_spreadsheet(spreadsheet_file_or_path, user, result):
    print("Ingesting spreadsheet")
    spreadsheetformat = infer_spreadsheet_type(spreadsheet_file_or_path)
    if spreadsheetformat == None:
        raise ValueError("Unknown Sheet Type, data not scraped")
    print("Guessed format as %s" % (spreadsheetformat,))
    spreadsheetiterator = SpreadsheetIterator(spreadsheet_file_or_path, spreadsheetformat, result)

    objects = {Obj.plural_name: {} for Obj in Object.get_object_types()}
    # Create
    print("Initializing Objects")
    for kwargs in spreadsheetiterator.iter_objects(update=False):
        obj_ids, create_kwargs, update_kwargs = Object._parse_kwargs(**kwargs)
        for Objs in obj_ids:
            Obj = Object.get_object_types(type_name=Objs)
            for obj_id in obj_ids[Objs]:
                # Skip if in cache
                if obj_id in objects[Objs]:
                    continue
                ckwargs = create_kwargs[Objs] if Objs in create_kwargs else {}
                obj = Obj.get_or_create(name=obj_id, **ckwargs).first()
                if not obj:
                    print("Warning: failed to get/create object")
                    print(obj_id, create_kwargs)
                    continue
                objects[Objs][obj_id] = obj
    # Update
    print("Updating Objects")
    for kwargs in spreadsheetiterator.iter_objects():
        obj_ids, create_kwargs, update_kwargs = Object._parse_kwargs(**kwargs)
        if not update_kwargs:
            continue
        for Objs in update_kwargs:
            for obj_id in obj_ids[Objs]:
                obj = objects[Objs][obj_id]
                obj.update(**update_kwargs[Objs])
    print("Putting in values")
    # Values
    for kwargs in spreadsheetiterator.iter_values():
        valClass = Value
        if "value_type" in kwargs:
            valClass = Value.get_value_types(type_name=kwargs["value_type"])
        value_kwargs = Value._parse_kwargs(**kwargs)
        try:
            vals = valClass.get_or_create(**value_kwargs)
        except Exception as e:
            print("Warning: failed to get/create value")
            print(kwargs)
            print(value_kwargs)
            print(e)
    return spreadsheetiterator.filename

class SpreadsheetIterator:
    def __init__(self, path_or_file, spreadsheetformat, result):
        self.result = result
        if isinstance(path_or_file, str):
            self.filename = path_or_file
            self.file = open(path_or_file,"r")
        else:
            self.filename = path_or_file.name
            self.file = path_or_file
        self.scraper = None
        sds = SpreadsheetDataScraper.for_format(spreadsheetformat)
        if sds:
            self.scraper = sds(self)

    def iter_objects(self, update=True):
        # Nothing universal to yank out
        # All work offloaded to scrapers
        if self.scraper:
            for record in self.scraper.iter_objects(update=update):
                yield record

    def iter_values(self):
        # Nothing universal to yank out
        # All work offloaded to scrapers
        if self.scraper:
            for record in self.scraper.iter_values():
                yield record

class SpreadsheetDataScraper:
    @classmethod
    def for_format(cls, format):
        for sc in cls.__subclasses__():
            if sc.sheet_format == format:
                return sc

class genoMICSampleDataSheet(SpreadsheetDataScraper):
    sheet_format = "genoMICSampleData"
    def __init__(self, si):
        self.table = pd.read_csv(si.filename)
        self.result = si.result

    @classmethod
    def compatible(cls, spreadsheet_path):
        if spreadsheet_path.endswith("tsv") or spreadsheet_path.endswith("csv"):
            table = pd.read_csv(spreadsheet_path)
        elif spreadsheet_file.endswith("xls"):
            table = pd.read_excel(spreadsheet_path)
        else:
            table = pd.read_table(spreadsheet_path)
        if "sequencing_id" in table.columns:
            return True
        else:
            return False

    def iter_objects(self, update=True):
        # Only feed out the sequencing ID as sample names for now
        for sample_name in self.table['sequencing_id']:
            yield {"sample_name": sample_name,
                   "result_name": self.result.name,
                   "result_sample": sample_name }

    def iter_values(self):
        data_type_library = {"site":"str",
                             "sample_location": "str",
                             "treatment":"str",
                             "preservation":"str",
                             "material":"str",
                             "control":"str",
                             "replicate":"int"}
        value_type_library = {"site":"location",
                             "sample_location": "location",
                             "treatment":"value",
                             "preservation":"value",
                             "material":"category",
                             "control":"value",
                             "replicate":"value"}
        value_columns = [x for x in self.table.columns if x not in ["sequencing_id", "sample_id"]]
        for row in self.table.itertuples():
            base_record = {"sample_name":row.sequencing_id, 
                           "result_name":self.result.name,
                           "value_object": "sample",
                           "value_object.1": "result"}
            for col_name in value_columns:
                value_data = getattr(row, col_name)
                #For this format, explicitly skip NA
                if value_data == "nan":
                    continue
                record = base_record.copy()
                record.update({"value_name":col_name, 
                               "value_data": value_data, 
                               "value_type":value_type_library[col_name],
                               "data_type":data_type_library[col_name]})
                yield record

class QUOREMBasicSheet(SpreadsheetDataScraper):
    sheet_format = "quoremBasic"
    def __init__(self, si):
        self.table = pd.read_csv(si.filename)
        self.result = si.result

    @classmethod
    def compatible(cls, spreadsheet_path):
        if spreadsheet_path.endswith("csv"):
            table = pd.read_csv(spreadsheet_path)
        elif spreadsheet_path.endswith("tsv"):
            table = pd.read_tsv(spreadsheet_path)
        elif spreadsheet_path.endswith("xls"):
            table = pd.read_excel(spreadsheet_path)
        else:
            table = pd.read_table(spreadsheet_path)
        object_headers = dict(Object.column_headings())
        for header in object_headers:
            # Just need one of the primary fields to be present, in theory
            # Not 100% bulletproof but it'll do
            if header in table.columns:
                if object_headers[header]:
                    return True
        return False

    def iter_objects(self, update=True):
        object_headers = dict(Object.column_headings())
        # Only feed out the sequencing ID as sample names for now
        for row in self.table.to_dict(orient="records"):
            record = {}
            for header in row.keys():
                if header in object_headers:
                    if update and not object_headers[header]:
                        record[header] = row[header]
                    if object_headers[header]:
                        record[header] = row[header]
            #Inject the spreadsheet
            record["result_name"] = self.result.name
            yield record

    def iter_values(self):
        for row in self.table.to_dict(orient="records"):
            if "value_name" not in row.keys():
                continue
            elif "value_data" not in row.keys():
                continue
            record = {}
            record["value_name"] = row["value_name"]
            record["value_data"] = row["value_data"]
            if "value_type" in row:
                record["value_type"] = row["value_type"]
            if "data_type" in row:
                record["data_type"] = row["data_type"]
            for header in row.keys():
                if header.startswith("value_object"):
                    record[header] = row[header]
                    if row[header] + "_name" not in row:
                        continue
                    record[row[header]+"_name"] = row[row[header]+"_name"]
            record["value_object.999"] = "result"
            record["result_name"] = self.result.name
            yield record

class QIIMEMetadataSheet(SpreadsheetDataScraper):
    sheet_format = "QIIME2Metadata"

