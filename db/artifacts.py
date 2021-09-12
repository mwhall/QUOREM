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

def base_uuid(filename):
    regex = re.compile("[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-" \
                       "[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}")
    return regex.match(filename)[0]

def qiime2_default_args(plugin_str, func_str):
    import qiime2
    pm = qiime2.sdk.PluginManager()
    if func_str in pm.plugins[plugin_str].methods:
        params = pm.plugins[plugin_str].methods[func_str].signature.parameters
        desc = pm.plugins[plugin_str].methods[func_str].description
    elif func_str in pm.plugins[plugin_str].visualizers:
        params = pm.plugins[plugin_str].visualizers[func_str].signature.parameters
        desc = pm.plugins[plugin_str].visualizers[func_str].description
    elif func_str in pm.plugins[plugin_str].pipelines:
        params = pm.plugins[plugin_str].pipelines[func_str].signature.parameters
        desc = pm.plugins[plugin_str].pipelines[func_str].description
    else:
        params = {}
        desc = "No description found"
    step_name = plugin_str + "__" + func_str
    for param in params:
        yield {"value_data": params[param].default,
               "value_name": param,
               "value_type": "parameter",
               "step_name": step_name,
               "value_object": "step"}
    yield {"value_data": desc,
           "value_name": "from_qiime2",
           "value_type": "description",
           "step_name": step_name,
           "value_object": "step"}

def qiime2_steps():
    import qiime2
    pm = qiime2.sdk.PluginManager()
    for ps in pm.plugins:
        for method in pm.plugins[ps].methods:
            yield {"step_name": ps+"__"+method}
        for viz in pm.plugins[ps].visualizers:
            yield {"step_name": ps+"__"+viz}
        for pipe in pm.plugins[ps].pipelines:
            yield {"step_name": ps+"__"+pipe}

def mine_qiime2():
    import qiime2
    for step_kwargs in qiime2_steps():
        obj_ids, create_kwargs, update_kwargs = Object._parse_kwargs(**step_kwargs)
        step_ids = obj_ids["steps"]
        step = Step.get_or_create(name=step_ids[0]).get() # NOTE: I don't pass create_kwargs here, so if qiime2_steps() feeds it anything detailed it'll get lost
        if "__" in step.name:
            plugin, cmd = step.name.split("__")
            for rec in qiime2_default_args(plugin, cmd):
                if type(rec["value_data"]) == qiime2.core.type.signature.__NoValueMeta:
                    continue
                if rec["value_data"]:
                    Value.get_or_create(**Value._parse_kwargs(**rec))

def ingest_artifact(artifact_file_or_path, analysis):
    artifactiterator = ArtifactIterator(artifact_file_or_path)
    # Cache
    objects = {Obj.plural_name: {} for Obj in Object.get_object_types()}
    # Create
    print("Initializing Objects")
    for kwargs in artifactiterator.iter_objects(update=False):
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
    print("Updating Objects")
    for kwargs in artifactiterator.iter_objects():
        obj_ids, create_kwargs, update_kwargs = Object._parse_kwargs(**kwargs)
        if not update_kwargs:
            continue
        for Objs in update_kwargs:
            for obj_id in obj_ids[Objs]:
                obj = objects[Objs][obj_id]
                obj.update(**update_kwargs[Objs])
    print("Putting in values")
    # Values
    for kwargs in artifactiterator.iter_values():
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
    return artifactiterator.base_uuid

def ingest_artifact_directory(directory, analysis, userprofile, sleep=1):
    directory = os.path.relpath(directory, settings.BASE_DIR)
    prev_dir = os.getcwd()
    os.chdir(settings.BASE_DIR +"/"+ directory)
    for file in os.listdir("."):
        if file.endswith(".qza") or file.endswith(".qzv"):
            print("Ingesting %s via celery" % (file,))
            upf = UploadFile(upload_file=File(open(file, 'rb')), userprofile=userprofile, upload_type="A")
            upf.save()
            current_app.send_task('db.tasks.react_to_file', (upf.pk,),
                      kwargs={'analysis_pk': analysis.pk})
        # Give this file a headstart to process in a concurrency scenario
            time.sleep(sleep)
    os.chdir(prev_dir)

class ArtifactIterator:
    def __init__(self, path_or_file):
        if isinstance(path_or_file, str):
            self.filename = path_or_file
        else:
            self.filename = path_or_file.name
        self.zfile = zipfile.ZipFile(path_or_file)
        self.infolist = self.zfile.infolist()
        self.base_uuid = base_uuid(self.infolist[0].filename)
        for uuid, yf in self.iter_metadatayaml():
            if (yf['uuid'] == self.base_uuid):
                self.base_format = yf["format"]
                self.base_type = yf["type"]
        self.scraper = None
        ads = ArtifactDataScraper.for_format(self.base_format)
        if ads:
            self.scraper = ads(self)

    def iter_objects(self, update=True):
        # Yields single records of artifact contents that describe QUOR'em Objects
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
                step_name = "qiime2_import"
                yield {"step_name": step_name}
                yield {"result_name": uuid,
                       "result_step": step_name}
                if 'manifest' in yf['action']:
                    for item in yf['action']['manifest']:
                        for prop, val in item.items():
                            if prop == 'name':
                                if re.compile('.*_S.*_L001_R[12]_001.fastq.gz').match(val):
                                    val = re.sub("_S.*_L001_R[12]_001.fastq.gz", "", val)
                                    yield {"result_name": uuid,
                                           "sample_name": val, 
                                           "sample_step": step_name,
                                           "result_sample": val,
                                           "result_step": step_name}
                                    yield {"result_name": self.base_uuid,
                                           "result_sample": val}
        if self.scraper:
            for record in self.scraper.iter_objects(update=update):
                yield record

    def iter_values(self):
        # Yields single records of artifact contents that are QUOR'em Values
        for uuid, yf in self.iter_metadatayaml():
            for x in ["type", "format"]:
                if yf[x] is not None:
                    yield {"result_name": yf['uuid'],
                           "value_name": "qiime2_%s" % (x,),
                           "value_type": "value",
                           "value_data": yf[x],
                           "value_object": "result"}
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
                step_name = "qiime2_import"
                if 'manifest' in yf['action']:
                    for item in yf['action']['manifest']:
                        if "name" in item:
                            val = item["name"]
                            for direc, num in [("forward", 1), ("reverse", 2)]:
                                if re.compile('.*_S.*_L001_R%d_001.fastq.gz'%(num,)).match(val):
                                    sample_name = str(re.sub("_S.*_L001_R[12]_001.fastq.gz", "", val))
                                    yield {"sample_name": sample_name,
                                            "value_object": "sample",
                                              "value_name": "%s_filename" % (direc,),
                                              "value_type": "file",
                                              "data_type": "str",
                                              "value_data": val}
                                    if ("md5sum" in item):
                                        val = item["md5sum"]
                                        yield {"sample_name": sample_name,
                                                  "value_name": "%s_file_md5sum" % (direc,),
                                                  "value_object": "sample",
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
                             "value_type": value_type,
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
        if self.scraper:
            for record in self.scraper.iter_values():
                yield record
        yield {"result_name": self.base_uuid,
               "value_name": "primary",
               "value_type": "description",
               "value_data": "QIIME2 %s file of type %s from Step %s" % (yf["action"]["type"], self.base_type, step_name),
               "value_object": "result"}

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

# Stub for Alex
#class PCoAResults(ArtifactDataScraper):
#    qiime_format = 'OrdinationDirectoryFormat'
#

class Dada2DenoiseStats(ArtifactDataScraper):
    qiime_format = 'DADA2StatsDirFmt'

    def __init__(self, ai):
        self.uuid = ai.base_uuid
        self.data_file = self.uuid + "/data/stats.tsv"
        xf = ai.zfile.open(self.data_file)
        self.tf = pd.read_csv(xf, sep="\t", comment="#", index_col=0)

    def iter_objects(self, update=True):
        for index, row in self.tf.iterrows():
            yield {"sample_name": str(index),
                   "result_name": self.uuid,
                   "sample_result": self.uuid}

    def iter_values(self):
        for index, row in self.tf.iterrows():
            for value_name, count in row.iteritems():
                yield {"result_name": self.uuid,
                        "value_name": value_name,
                        "value_data": count,
                        "value_type": "measure",
                        "data_type": "int",
                        "sample_name": str(index),
                        "value_object": "result",
                        "value_object.1": "sample"}

class PhylogeneticTree(ArtifactDataScraper):
    qiime_format = 'NewickDirectoryFormat'

    def __init__(self, ai):
        self.uuid = ai.base_uuid
        self.data_file = self.uuid + "/data/tree.nwk"
        xf = ai.zfile.open(self.data_file)
        self.newick = xf.read().decode()
        self.tree = ete3.Tree(self.newick, format=1)

    def iter_objects(self, update=True):
        for leaf in self.tree.iter_leaves():
            yield {"feature_name": str(leaf.name.strip("'")),
                   "result_name": self.uuid,
                   "feature_result": self.uuid}

    def iter_values(self):
        yield {"result_name": self.uuid,
               "value_name": "newick",
               "value_type": "tree",
               "value_data": self.newick,
               "data_type": "newicktree",
               "value_object": "result"}

class BetaDiversity(ArtifactDataScraper):
    qiime_format = 'DistanceMatrixDirectoryFormat'

    def __init__(self, ai):
        self.uuid = ai.base_uuid
        self.data_file = self.uuid + "/data/distance-matrix.tsv"
        xf = ai.zfile.open(self.data_file)
        self.tf = pd.read_csv(xf, sep="\t", index_col=0)

    def iter_objects(self, update=True):
        for index, row in self.tf.iterrows():
            yield {"sample_name": str(index),
                   "result_name": self.uuid,
                   "sample_result": self.uuid}

    def iter_values(self):
        for index, row in self.tf.iterrows():
            for col, dist in row.iteritems():
                if index != col: # Don't store identities
                    yield {"result_name": self.uuid,
                           "sample_name": str(index),
                           "sample_name.1": str(col),
                           "value_data": dist,
                           "data_type": "float",
                           "value_name": "beta_diversity",
                           "value_type": "measure",
                           "value_object": "sample",
                           "value_object.1": "result"}

class AlphaDiversity(ArtifactDataScraper):
    qiime_format = 'AlphaDiversityDirectoryFormat'

    def __init__(self, ai):
        self.uuid = ai.base_uuid
        self.data_file = self.uuid + "/data/alpha-diversity.tsv"
        xf = ai.zfile.open(self.data_file)
        self.tf = pd.read_csv(xf, sep="\t", index_col=0)

    def iter_values(self):
        measure = self.tf.columns[0]
#        yield {"result_name": self.uuid,
#               "step_name": "diversity__alpha",
#               "value_object.1": "step",
#               "value_name": "metric",
#               "value_type": "parameter",
#               "value_data": measure,
#               "value_object": "result",
#               "data_type": "str"}
        for index, row in self.tf.iterrows():
            yield {"result_name": self.uuid,
                   "value_name": "alpha_diversity",
                   "value_type": "measure",
                   "value_data": row[measure],
                   "sample_name": str(index),
                   "value_object": "result",
                   "value_object.1": "sample",
                   "data_type": "float"}

    def iter_objects(self, update=True):
        for index, row in self.tf.iterrows():
            yield {"sample_name": str(index),
                   "result_name": self.uuid,
                   "sample_result": self.uuid}


class Taxonomy(ArtifactDataScraper):
    qiime_format = 'TSVTaxonomyDirectoryFormat'

    def __init__(self, ai):
        self.uuid = ai.base_uuid
        self.data_file = self.uuid + "/data/taxonomy.tsv"
        xf = ai.zfile.open(self.data_file)
        self.tf = pd.read_csv(xf, sep="\t")

    def iter_data(self):
        for index, row in self.tf.iterrows():
            tax = row['Taxon']
            conf = row['Confidence']
            feat = row['Feature ID']
            yield (feat, tax, conf)

    def iter_values(self):
        for feat, tax, conf in self.iter_data():
            #Same for all records being generated
            yield {"result_name": self.uuid,
                   "value_object": "result",
                   "value_object.1": "feature",
                   "feature_name": str(feat),
                   "value_type": "measure",
                   "value_name": "taxonomic_classification",
                   "value_data": tax,
                   "data_type": "str"}
            yield {"result_name": self.uuid,
                   "value_object": "result",
                   "value_object.1": "feature",
                   "feature_name": str(feat),
                   "value_type": "measure",
                   "value_name": "confidence",
                   "value_data": conf,
                   "data_type": "float"}

    def iter_objects(self, update=True):
        for feat, tax, conf in self.iter_data():
            yield {"feature_name": feat,
                   "result_name": self.uuid,
                   "feature_result": self.uuid}

class FeatureTable(ArtifactDataScraper):
    qiime_format = 'BIOMV210DirFmt'

    def __init__(self, ai):
        self.uuid = ai.base_uuid
        self.coo_mat, self.samples, self.features = self.get_data(ai)
        for uuid, yf in ai.iter_actionyaml():
            if uuid == self.uuid:
                plugin = yf['action']['plugin'].split(":")[-1]
        if plugin in ['dada2', "deblur"]:
            self.value_name = "asv_table"
        elif plugin == "vsearch":
            self.value_name = "otu_table"
        elif plugin == "diversity":
            self.value_name = "rarefied_table"
        else:
            self.value_name = "feature_table"

    def iter_objects(self, update=True):
        feature_names = self.features.values_list("name", flat=True)
        feature_dict = dict(self.features.values_list("pk", "name"))
        record = {"result_name": self.uuid}
        record.update({"result_feature.%d" % (idx,): feature for idx, feature in enumerate(feature_names)})
        record.update({"feature_name.%d" % (idx,): feature for idx, feature in enumerate(feature_names)})
        yield record
        sample_names = self.samples.values_list("name", flat=True)
        record = {"result_name": self.uuid}
        record.update({"sample_name.%d" % (idx,): sample for idx, sample in enumerate(sample_names)})
        record.update({"result_sample.%d" % (idx,): sample for idx, sample in enumerate(sample_names)})
        yield record
        if update:
            for sample in self.samples.all():
                record = {"sample_name": str(sample.name)}
                features_present = self.coo_mat.getcol(sample.pk).tocoo().row
                record.update({"sample_feature.%d" % (idx,): feature_dict[pk] for idx, pk in enumerate(features_present)})
                yield record

    def iter_values(self):
        # Infer the table type if we can
        self.coo_mat.colobj = "sample"
        self.coo_mat.rowobj = "feature"
        record = {"result_name": self.uuid,
                  "value_name": self.value_name,
                  "value_object": "result",
                  "value_object.0": "sample",
                  "value_object.1": "feature",
                  "value_type": "matrix",
                  "data_type": "coomatrix",
                  "value_data": self.coo_mat}
        record.update({"sample_name.%d" % (idx,): str(sample.name) for idx, sample in enumerate(self.samples)})
        record.update({"feature_name.%d" % (idx,): feature.name for idx, feature in enumerate(self.features)})
        yield record

    def get_data(self, ai):
        data_file = ai.base_uuid + "/data/feature-table.biom"
        with tempfile.NamedTemporaryFile() as temp_file:
            x=ai.zfile.read(data_file)
            temp_file.write(x)
            tf = h5.File(temp_file.name)
            data = tf['observation/matrix/data'][:]
            indptr = tf['observation/matrix/indptr'][:]
            indices = tf['observation/matrix/indices'][:]
            sample_ids = tf['sample/ids'][:]
            feature_ids = tf['observation/ids'][:]
        feature_ids = [x.decode() for x in feature_ids]
        sample_ids = [x.decode() for x in sample_ids]
        csr_mat = csr_matrix((data,indices,indptr))
        # We have to convert the names in the BIOM files to database PKs for the
        # matrix
        coo_mat = csr_mat.tocoo()
        # We can release the h5 file at this point: we have all we need from it
        samples = Sample.objects.filter(name__in=sample_ids)
        features = Feature.objects.filter(name__in=feature_ids)
        found_samples = dict(samples.values_list("name", "pk"))
        found_features = dict(features.values_list("name", "pk"))
        sample_pks = {}
        feature_pks = {}
        for idx, sample in enumerate(sample_ids):
            if sample not in found_samples:
                new_samples = Sample.create(name=sample)
                sample_pks[idx] = new_samples.first().pk
                samples = samples | new_samples
            else:
                sample_pks[idx] = found_samples[sample]
        for idx, feature in enumerate(feature_ids):
            if feature not in found_features:
                new_features = Feature.create(name=feature)
                feature_pks[idx] = new_features.first().pk
                features = features | new_features
            else:
                feature_pks[idx] = found_features[feature]
        row = [feature_pks[x] for x in coo_mat.row]
        col = [sample_pks[x] for x in coo_mat.col]
        coo_mat = coo_matrix((coo_mat.data, (row, col)))
        return coo_mat, samples, features



