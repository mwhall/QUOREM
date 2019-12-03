import zipfile
import yaml
import re
import os

import pandas as pd

from .models.object import Object
from .models.value import Value

def scalar_constructor(loader, node):
    value = loader.construct_scalar(node)
    return value

yaml.add_constructor('!ref', scalar_constructor)
yaml.add_constructor('!no-provenance', scalar_constructor)
yaml.add_constructor('!color', scalar_constructor)
yaml.add_constructor('!cite', scalar_constructor)
yaml.add_constructor('!metadata', scalar_constructor)

def base_uuid(filename):
    regex = re.compile("[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-" \
                       "[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}")
    return regex.match(filename)[0]

def ingest_artifact(artifact_file_or_path, analysis):
    artifactiterator = ArtifactIterator(artifact_file_or_path)
    # Cache
    objects = {Obj.plural_name: {} for Obj in Object.get_object_types()}
    # Create
    for kwargs in artifactiterator.iter_objects():
        obj_ids, create_kwargs, update_kwargs = Object._parse_kwargs(**kwargs)
        if "results" in create_kwargs:
            create_kwargs["results"]["analysis"] = analysis
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
    for kwargs in artifactiterator.iter_objects():
        obj_ids, create_kwargs, update_kwargs = Object._parse_kwargs(**kwargs)
        if not update_kwargs:
            continue
        for Objs in update_kwargs:
            for obj_id in obj_ids[Objs]:
                obj = objects[Objs][obj_id]
                obj.update(**update_kwargs[Objs])
    # Values
    for kwargs in artifactiterator.iter_values():
        value_kwargs = Value._parse_kwargs(**kwargs)
        try:
            vals = Value.get_or_create(**value_kwargs)
        except:
            print("Warning: failed to get/create value")
            print(kwargs)
            print(value_kwargs)
    return artifactiterator.base_uuid

class ArtifactIterator:
    def __init__(self, path_or_file):
        if isinstance(path_or_file, str):
            self.filename = path_or_file
        else:
            self.filename = path_or_file.name
        self.zfile = zipfile.ZipFile(path_or_file)
        self.infolist = self.zfile.infolist()
        self.base_uuid = base_uuid(self.infolist[0].filename)

    def iter_objects(self):
        # Yields single records of artifact contents that describe QUOR'em Objects
        for uuid, yf in self.iter_metadatayaml():
            for x in ["type", "format"]:
                if (yf['uuid'] == self.base_uuid):
                    if x=="format":
                        base_format = yf[x]
                    else:
                        base_type = yf[x]
        for uuid, yf in self.iter_actionyaml():
            if yf['action']['type'] in ['method', 'pipeline', 'visualizer']:
                step_name = yf['action']['plugin'].split(":")[-1] +\
                               "__" + yf['action']['action']
                yield {"step_name": step_name}
                record = {"result_name": uuid,
                          "result_step": step_name}
                upstream = ({x: y for x,y in 
                               {"result_upstream.%d" % (idx,): uid.popitem()[1] 
                                for idx, uid in enumerate(yf['action']['inputs'])}.items() 
                                if y is not None})
                record.update(upstream)
                yield record
            elif yf['action']['type'] == 'import':
                yield {"step_name": "qiime2_import"}
                yield {"result_name": uuid,
                       "result_step": "qiime2_import"}
                for item in yf['action']['manifest']:
                    for prop, val in item.items():
                        if prop == 'name':
                            if re.compile('.*_S0_L001_R[12]_001.fastq.gz').match(val):
                                val = re.sub("_S0_L001_R[12]_001.fastq.gz", "", val)
                                yield {"result_name": uuid,
                                       "sample_name": val, 
                                       "sample_step": "qiime2_import",
                                       "result_sample": val,
                                       "result_step": "qiime2_import"}
                                yield {"result_name": self.base_uuid,
                                       "result_sample": val}

        ads = ArtifactDataScraper.for_format(base_format)
        if ads:
            for record in ads.iter_objects(self):
                yield record

    def iter_values(self):
        # Yields single records of artifact contents that are QUOR'em Values
        for uuid, yf in self.iter_metadatayaml():
            for x in ["type", "format"]:
                yield {"result_name": yf['uuid'],
                       "value_name": "qiime2_%s" % (x,),
                       "value_type": "value",
                       "value_data": yf[x],
                       "value_object": "result"}
                if (yf['uuid'] == self.base_uuid):
                    if x=="format":
                        base_format = yf[x]
                    else:
                        base_type = yf[x]
        for uuid, yf in self.iter_actionyaml():
            if yf['action']['type'] in ['method', 'pipeline', 'visualizer']:
                step_name = yf['action']['plugin'].split(":")[-1] + \
                               "__" + yf['action']['action']
                for pdict in yf["action"]["parameters"]:
                    for name, data in pdict.items(): # These are all apparently one item dicts
                        if data:
                            yield {"result_name": uuid,
                                     "value_object": "result",
                                     "step_name": step_name,
                                     "value_object.1": "step",
                                     "value_name": name,
                                     "value_data": data,
                                     "value_type": "parameter"}
                if yf['action']['type'] == "pipeline":
                    yield {"result_name": uuid,
                           "value_object": "result",
                           "value_name": "alias_of",
                           "value_type": "value",
                           "value_data": yf["action"]["alias-of"],
                           "data_type": "auto"}
            elif yf['action']['type'] == 'import':
                for item in yf['action']['manifest']:
                    if "name" in item:
                        val = item["name"]
                        for direc, num in [("forward", 1), ("reverse", 2)]:
                            if re.compile('.*_S0_L001_R%d_001.fastq.gz'%(num,)).match(val):
                                sample_name = re.sub("_S0_L001_R[12]_001.fastq.gz", "", val)
                                yield {"sample_name": sample_name, 
                                          "value_name": "%s_filename" % (direc,),
                                          "value_type": "file",
                                          "data_type": "str",
                                          "value_data": val}
                                if ("md5sum" in item):
                                    val = item["md5sum"]
                                    yield {"sample_name": sample_name,
                                              "value_name": "%s_file_md5sum" % (direc,),
                                              "value_type": "value",
                                              "value_data": val,
                                              "data_type": "str"}
            yield {"result_name": uuid,
                      "value_object": "result",
                      "value_name": "runtime",
                      "value_type": "measure",
                      "value_data": yf["execution"]["runtime"]["duration"],
                      "data_type": "time"}
            for name in ["duration", "start", "end"]:
                data_type = "time" if (name=="duration") else "datetime"
                value_type = "measure" if (name=="duration") else "date"
                yield {"result_name": uuid,
                         "value_object": "result",
                             "value_name": name,
                             "value_type": "date",
                             "value_data": yf["execution"]["runtime"][name],
                             "data_type": data_type}
            if type(yf["environment"]["framework"]) == str:
                qiime_version = yf["environment"]["framework"]
            else:
                qiime_version = yf["environment"]["framework"]["version"]
            yield {"result_name": uuid,
                          "value_object": "result",
                          "value_name": "qiime2", 
                          "value_type": "version",
                          "data_type": "auto",
                          "value_data": qiime_version}
            for plugin in yf["environment"]["plugins"]:
                version = yf["environment"]["plugins"][plugin]["version"]
                yield {"result_name": uuid,
                          "value_object": "result",
                          "value_name": "q2-" + plugin, 
                          "value_type": "version",
                          "data_type": "auto", #Don't force this because lots will violate and need to default to StrDatum
                          "value_data": version}
            for pkg in yf["environment"]["python-packages"]:
                version = yf["environment"]["python-packages"][pkg]
                yield {"result_name": uuid,
                          "value_object": "result",
                          "value_name": pkg, 
                          "value_type": "version",
                          "data_type": "auto",
                          "value_data": version}
        ads = ArtifactDataScraper.for_format(base_format)
        if ads:
            for record in ads.iter_values(self):
                yield record

    def iter_actionyaml(self):
        actions = ["action/action.yaml"]
        for fname in self.infolist:
            regex = re.compile("[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-" \
                               "[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}/action/action.yaml")
            matches = regex.findall(fname.filename)
            if len(matches) >= 1:
                actions.append("artifacts/" + matches[0])
        for ayaml in actions:
            xf = self.zfile.open(self.base_uuid + "/provenance/" + ayaml)
            yf = yaml.load(xf, Loader=yaml.Loader)
            if ayaml == "action/action.yaml":
                uuid = self.base_uuid
            else:
                uuid = ayaml.split("/")[1]
            yield (uuid, yf)

    def iter_metadatayaml(self):
        metadata = [self.base_uuid+"/metadata.yaml"]
        for fname in self.infolist:
            regex = re.compile("[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-" \
                               "[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}.*/artifacts/.*metadata.yaml")
            matches = regex.findall(fname.filename)
            if len(matches) >= 1:
                metadata.append(matches[0])
        for myaml in metadata:
            xf = self.zfile.open(myaml)
            yf = yaml.load(xf, Loader=yaml.Loader)
            if myaml == self.base_uuid + "/metadata.yaml":
                uuid = self.base_uuid
            else:
                uuid = myaml.split("/")[3]
            yield (uuid, yf)

class ArtifactDataScraper:
    @classmethod
    def for_format(cls, format):
        for sc in cls.__subclasses__():
            if sc.qiime_format == format:
                return sc

class Taxonomy(ArtifactDataScraper):
    qiime_format = 'TSVTaxonomyDirectoryFormat'

    @classmethod
    def iter_data(cls, ai):
        data_file = ai.base_uuid + "/data/taxonomy.tsv"
        xf = ai.zfile.open(data_file)
        tf = pd.read_csv(xf, sep="\t")
        for index, row in tf.iterrows():
            tax = row['Taxon']
            conf = row['Confidence']
            feat = row['Feature ID']
            yield (feat, tax, conf)

    @classmethod
    def iter_values(cls, ai):
        for feat, tax, conf in cls.iter_data(ai):
            #Same for all records being generated
            base_dict = {"result_name": ai.base_uuid,
                         "value_object": "result",
                         "value_object.1": "feature",
                         "feature_name": feat,
                         "value_type": "measure"}
            #Additional bits
            exp_dicts = [ {"value_name": "taxonomic_classification",
                           "value_data": tax,
                           "data_type": "str"},
                          {"value_name": "confidence",
                           "value_data": conf,
                           "data_type": "float"}]
            for ed in exp_dicts:
                nd = base_dict.copy()
                nd.update(ed)
                yield nd

    @classmethod
    def iter_objects(cls, ai):
        for feat, tax, conf in cls.iter_data(ai):
            yield {"feature_name": feat,
                   "result_name": ai.base_uuid,
                   "feature_result": ai.base_uuid} # Result goes last
        
