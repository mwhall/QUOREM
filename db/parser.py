import arrow
import uuid
import pandas as pd
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from .models import Investigation, Sample, Process, Step, Analysis, \
                    Feature, Category, Value, Result, StrVal, IntVal, FloatVal, \
                    DatetimeVal, ResultVal


base_names = ["investigation", "process", "step", \
              "analysis", "sample", "feature", "result"]

id_fields = [ x + "_id" for x in base_names ]

category_fields = [ x + "_category" for x in base_names ]

upstream_models = ["process", "step", "sample", "result"]
upstream_fields = [ "upstream_" + x for x in upstream_models ]

reserved_fields = id_fields + \
                  category_fields + \
                  upstream_fields + \
                  ["investigation_description", \
                   "investigation_citation", \
                   "investigation_institution", \
                   "process_description", \
                   "process_citation", \
                   "step_description", \
                   "result_type", \
                   "result_source", \
                   "analysis_location", \
                   "analysis_date", \
                   "extra_step", \
                   "feature_sequence", \
                   "value_type", \
                   "value_target", \
                   "force_overwrite"]

linkable_fields = id_fields + ["extra_step"]

plural_mapper = {"investigation": "investigations",
                 "process": "processes",
                 "step": "steps",
                 "analysis": "analyses",
                 "result": "results",
                 "sample": "samples",
                 "feature": "features"}

def resolve_target(row):
    precedence = ["result_id", "step_id", "sample_id", "process_id", "analysis_id", \
                  "investigation_id", "feature_id"]
    for id_field in precedence:
        if id_field in row:
            return id_field

class MissingColumnError(Exception):
    """Error for when a column that should be present in order to commit a row
    is not present"""
    pass

class InvalidNameError(Exception):
    """Error for when an id is not a valid name; typically when it is an
    integer, as these are reserved for primary keys"""
    pass

class InconsistentWithDatabaseError(Exception):
    """Error for when an id is found but the other fields don't match
    what is in the database"""
    pass

class AmbiguousInputError(Exception):
    pass

class NotFoundError(Exception):
    pass

class DuplicateEntryError(Exception):
    pass

class DuplicateTypeError(Exception):
    pass

#Generic Validator functions go here
class Validator():
    value_field = None

    def __init__(self, data=pd.Series({})):
        self.data = data
        assert isinstance(self.data, pd.Series)
        #NOTE: The way we input/loop through data, duplicate columns/indexes are allowed in self.data
        # Calls to self.data should either be loops over indices, or unambiguous/non-duplicate fields ONLY
        assert (self.data.index==self.id_field).sum() == 1, "Cannot have duplicate primary targets for a validator"
        if "force_overwrite" in self.data:
            self.overwrite = True
        else:
            self.overwrite = False
        self.required_if_new = []
        self.optional_fields = []
        self.manytomany_fields = []
        self.django_mapping = {}

    def in_db(self):
        """Base Validator in database check
           id_field is the value in the id_field for this modeil """
        kwargs = {self.django_mapping[self.id_field] + "__exact": self.data[self.id_field]}
        return self.model.objects.filter(**kwargs).exists()

    def validate(self):
        in_db = self.in_db()
        #If not in database, make sure we have all the fields to save it
        if (not in_db):
            #If the investigation can't be found, we need to create it, and
            #that requires an institution and description
            missing_fields = [ x for x in self.required_if_new \
                                                   if x not in self.data ]
            if len(missing_fields) > 0:
                raise MissingColumnError("Columns " + \
                        ", ".join(missing_fields) + " missing and required")

            for field in self.required_if_new + self.optional_fields:
                if field == "extra_step":
                    field = "step_id"
                if (field != self.id_field) and (field in id_fields) and (field in self.data):
                    data = self.data.drop(self.id_field)
                    vldtr = validator_mapper[field.split("_")[0]](data=data)
                    vldtr.validate()

        #if in database, make sure all their available data matches ours,
        #if not it's mistaken identity
        else:
            try:
                self.fetch(id_only=False)
            except self.model.DoesNotExist:
                raise InconsistentWithDatabaseError("%s id %s found in database, \
                    but other %s fields do not exactly match database values.\
                    Value: %s. If you know the id is correct, remove the other %s fields\
                    and it will submit to that %s." % (self.model_name,
                                                       self.id_field,
                                                       self.model_name,
                                                       self.data[self.id_field],
                                                       self.model_name,
                                                       self.model_name))
        return True

    def fetch(self, id_only=True):
        """Does an exact fetch on all kwargs
           If kwargs[self.id_field] is an int then it queries that as pk"""
        kwargs = {self.django_mapping[self.id_field] + "__exact": self.data[self.id_field]}
        if id_only:
            return self.model.objects.get(**kwargs)
        else:
            for field, datum in self.data.iteritems():
                if pd.isna(datum):
                    #Ignore it for this row
                    continue
                if field in self.required_if_new + self.optional_fields:
                    #NOTE: This doesn't fetch Categories, Values, or Upstream/Downstream, which is OK for fetching, I think
                    if field in id_fields:
                        if field == self.id_field:
                            # This is asserted to be unique
                            name = field
                            name_field = self.django_mapping[field] + "__exact"
                        else:
                            # This may not be unique, so we have to slice it down to only the ID
                            vldtr = validator_mapper[field.split("_")[0]](data=pd.Series({field: self.data[field]}))
                            name = vldtr.fetch()
                            name_field = self.django_mapping[field]
                        if field not in self.manytomany_fields:
                            #Then it is its own argument, and not a list/set argument
                            kwargs[name_field] = name
                        else:
                            pass #TODO: Do we add them to a list, and use the mapping to check if they are present? Can Django handle this naturally?
                    else:
                        if field not in self.manytomany_fields:
                            kwargs[self.django_mapping[field] + "__exact"] =  datum
                        else:
                            pass #TODO: see above
        return self.model.objects.get(**kwargs)

    def save(self):
        #Go through each field
        kwargs = {self.django_mapping[self.id_field]: self.data[self.id_field]}
        in_db = self.in_db()
        m2m_links = []
        categories_to_add = []
        upstream_to_add = []
        
        for field, datum in self.data.iteritems():
            if pd.isna(datum):
                #Irrelevant field for this row/validator
                continue
            #If x is an id field, then we have to fetch the actual object
            if (field in self.required_if_new + self.optional_fields) and (field in id_fields) and (field != self.id_field):
                # Keep all other context the same, but focus on this object
                data = self.data.drop(field)
                # Remove the original id_field that we're saving so we don't recurse forever
                data = data.drop(self.id_field)
                data[field] = datum
                vldtr = validator_mapper[field.split("_")[0]](data=data)
                if vldtr.in_db():
                    datum = vldtr.fetch()
                else:
                    # We have to make it
                    datum = vldtr.save()
            elif (field in category_fields) and (field == self.id_field.split("_")[0] + "_category"):
                # Grab the category, or make it if it's new
                model_name = field.split("_")[0]
                assert model_name in validator_mapper
                content_type = ContentType.objects.get(app_label='db', 
                                                       model=model_name)
                cat_exists = Category.objects.filter(category_of=content_type, 
                                                     name=datum).exists()
                if not cat_exists:
                    cat = Category(category_of=content_type, name=datum)
                    cat.save()
                else:
                    cat = Category.objects.get(category_of=content_type, 
                                               name=datum)
                categories_to_add.append(cat)
            elif (field in upstream_fields) and (field in self.django_mapping):
                # Grab the upstream item, depending on what it is
                model_name = field.split("_")[1]
                vldtr = validator_mapper[field.split("_")[1]](data=pd.Series({model_name + "_id": datum}))
                upobj = vldtr.fetch()
                upstream_to_add.append(upobj)
            if field in self.manytomany_fields:
                m2m_links.append((field, datum))
            elif (field not in upstream_fields) and (field not in category_fields) and (field in self.django_mapping):
                kwargs[self.django_mapping[field]] = datum
        
        #Now that we've collected all the things, we can make it if it isn't in the DB
        if not in_db:
            try:
                obj = self.model(**kwargs)
                obj.save()
            except:
                raise
        else:
            try:
                obj = self.fetch(id_only=False)
            except self.model.DoesNotExist:
                raise InconsistentWithDatabaseError("Cannot save changes to requested object: An item with the same ID but differing values from this input exists in the database. Refusing to overwrite.")
        # If we can find the things, add/update the requested catgories, upstream, and other m2m fields
        for field, datum in m2m_links:
            getattr(obj, self.django_mapping[field]).add(datum)
        #Commit categories
        for cat in categories_to_add:
            obj.categories.add(cat)
        #Commit upstream links
        for upobj in upstream_to_add:
            obj.upstream.add(upobj)
        return obj

class InvestigationValidator(Validator):
    model_name = "Investigation"
    model = Investigation
    value_field = "values"
    id_field = "investigation_id"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_if_new = ["investigation_institution",
                                "investigation_description"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "institution",
                               self.required_if_new[1]: "description"}

class SampleValidator(Validator):
    model_name = "Sample"
    model = Sample
    value_field = "values"
    id_field = "sample_id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_if_new = ["investigation_id", "process_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "investigation",
                               self.required_if_new[1]: "process",
                               "upstream_sample": "upstream"}

class FeatureValidator(Validator):
    model_name = "Feature"
    model = Feature
    value_field = "values"
    id_field = "feature_id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_if_new = []
        self.optional_fields = ["feature_sequence", "result_id", "sample_id"]
        self.manytomany_fields = ["result_id", "sample_id"]
        self.django_mapping = {self.id_field: "name",
                               self.optional_fields[0]: "sequence",
                               self.optional_fields[1]: "observed_results",
                               self.optional_fields[2]: "observed_samples"}

class ProcessValidator(Validator):
    model_name = "Process"
    model = Process
    value_field = "parameters"
    id_field = "process_id"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_if_new = ["process_description", "process_citation"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "description",
                               self.required_if_new[1]: "citation",
                               "upstream_process": "upstream"}

class StepValidator(Validator):
    model_name = "Step"
    model = Step
    value_field = "parameters"
    id_field = "step_id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_if_new = ["process_id",
                                "step_description"]
        self.manytomany_fields = ["process_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "processes",
                               self.required_if_new[1]: "description",
                               "upstream_step": "upstream"}

class AnalysisValidator(Validator):
    model_name = "Analysis"
    model = Analysis
    value_field = "values"
    id_field = "analysis_id"

    def __init__(self, date_format = "DD/MM/YYYY", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_if_new = ["process_id"]
        self.manytomany_fields = ["extra_step"]
        self.optional_fields = ["analysis_location", "analysis_date", "extra_step"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "process",
                               self.manytomany_fields[0]: "extra_steps",
                               self.optional_fields[0]: "location",
                               self.optional_fields[1]: "date"}
        # Transform the date to Django's default format
        if "analysis_date" in self.data:
            try:
                self.data["analysis_date"] = arrow.get(self.data["analysis_date"], date_format).format("YYYY-MM-DD")
            except arrow.parser.ParserError:
                try: 
                    self.data["analysis_date"] = arrow.get(self.data["analysis_date"], "YYYY-MM-DD").format("YYYY-MM-DD")
                except arrow.parser.ParserError:
                    raise ValueError("Can't parse analysis_date with arrow")

# Tried to do this with a purely class-based method, but it took too much time
# Overriding for this one, because it's different enough
class ResultValidator(Validator):
    model_name = "Result"
    model = Result
    value_field = "values"
    id_field = "result_id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #NOTE: Generating of UUIDs, if necessary, is handled at spreadsheet parse in db/formatters.py
        #If values are UUIDs, they are not changed
        #If values are not UUIDs, they are replaced with a UUID, with the same value being replaced with the same UUID
        #If result_id is totally blank in the sheet, one UUID is generated for the whole column
        # Don't leave result_id blank unless you intend to submit a result_id with every row!
        self.required_if_new = ["result_type",
                                "result_source",
                                "analysis_id",
                                "step_id"]
        self.optional_fields = ["sample_id", "feature_id"]
        self.manytomany_fields = ["sample_id", "feature_id"]
        self.django_mapping = {self.id_field: "uuid",
                               self.required_if_new[0]: "type",
                               self.required_if_new[1]: "source",
                               self.required_if_new[2]: "analysis",
                               self.required_if_new[3]: "source_step__name",
                               self.manytomany_fields[0]: "samples",
                               self.manytomany_fields[1]: "features",
                               "upstream_result": "upstream"}

    def fetch(self, id_only=True):
        #Even though I propagate id_only here, it isn't needed since
        # the UUID should help maintain certainty of uniqueness
        return Result.objects.get(uuid=self.data["result_id"])
            

    def in_db(self):
        return Result.objects.filter(uuid=self.data["result_id"]).exists()

    def validate(self, save=False):
        # First check that the process and source step exist
        if not self.in_db():
            data = self.data.copy()
            data = data.drop("result_id")
            analysis_vldtr = AnalysisValidator(data=data)
            analysis_vldtr.validate()
            if not analysis_vldtr.in_db():
                # This must be saved before we can validate ourselves
                analysis_vldtr.save()
            data = data.drop("analysis_id")
            step_vldtr = StepValidator(data=data)
            step_vldtr.validate()
            if save and (not step_vldtr.in_db()):
                step_vldtr.save()
            for field, datum in self.data.iteritems():
                if field == "sample_id":
                    samp_vldtr = SampleValidator(data=pd.Series({"sample_id": datum}))
                    samp_vldtr.validate()
                    if save and (not samp_vldtr.in_db()):
                        samp_vldtr.save()
                elif field == "feature_id":
                    feat_vldtr = FeatureValidator(data=pd.Series({"feature_id": datum}))
                    feat_vldtr.validate()
                    if save and (not feat_vldtr.in_db()):
                        feat_vldtr.save()
                elif field == "upstream_result":
                    res_vldtr = ResultValidator(data=pd.Series({"result_id": datum}))
                    #If we use validate here, theres a chance it'll pass it based on the result's analysis etc.
                    if not res_vldtr.in_db():
                        raise NotFoundError("Result %s not found in database, cannot add to upstream" % (res_vldtr.data["result_id"],))
                    
        return True

    def save(self):
        self.validate(save=True)
        analysis = AnalysisValidator(data=pd.Series({"analysis_id": self.data["analysis_id"]})).fetch()
        source_step = StepValidator(data=pd.Series({"step_id": self.data["step_id"]})).fetch()
        samples = Sample.objects.filter(name__in=[y for x,y in self.data.iteritems() if x=="sample_id"])
        features = Feature.objects.filter(name__in=[y for x,y in self.data.iteritems() if x=="feature_id"])
        upstream = Result.objects.filter(uuid__in=[y for x,y in self.data.iteritems() if x=="upstream_result"])
        categories = Category.objects.filter(name__in=[y for x,y in self.data.iteritems() if x=="result_category"],
                                             category_of=ContentType.objects.get(app_label='db', model='result'))
        if not self.in_db():
            result = Result(uuid=self.data["result_id"],
                            source_step = source_step,
                            source = self.data["result_source"],
                            type = self.data["result_type"],
                            analysis = analysis)
            result.save()
        else:
            result = self.fetch()
        result.samples.add(*samples)
        result.features.add(*features)
        result.upstream.add(*upstream)
        result.categories.add(*categories)
        #TODO:
        # If source_step not in analysis.process, then it must be added to analysis.extra_steps

def existing_type(model, name):
    #Get all objects of this container/object type combo
    objs = model.objects.get(name__exact = name)
    if len(objs) == 0:
        return None
    else:
        for otype in ["str", "int", "float", "date", "result"]:
            if otype in objs[0].fields:
                return otype

def typecast(type_str):
    if type_str=="strval":
        return str
    elif type_str=="intval":
        return int
    elif type_str=="floatval":
        return float
    elif type_str=="datetimeval":
        return arrow.get
    elif type_str=="resultval":
        return uuid.UUID

class ValueValidator(Validator):
    def __init__(self, name, date_format = "DD/MM/YYYY", *args, **kwargs):
        self.id_field = name
        super().__init__(*args, **kwargs)
        self.TYPE_FIELD_MAP = {"strval": "str",
                               "intval": "int",
                               "floatval": "float",
                               "datetimeval": "date",
                               "resultval": "result"}
        self.TYPE_MODEL_MAP = {"strval" : StrVal,
                               "intval": IntVal,
                               "floatval": FloatVal,
                               "datetimeval": DatetimeVal,
                               "resultval": ResultVal}
        if "value_type" not in self.data:
            raise ValueError("Generic Value column %s without a 'value_type' column" % (name,))
        self.date_format = date_format

        # Measure, Metadata, Parameter
        self.vtype = self.data["value_type"]
        if self.vtype not in dict(Value.VALUE_TYPES):
            raise ValueError("vtype must be one of %s" % (str(
                                                          list(
                                                          dict(
                                        Value.VALUE_TYPES).keys())),))
        self.value = self.data[name]
        self.type = self.infer_type()
        self.value_caster = typecast(self.type)
        if self.type is not "datetimeval":
            self.casted_value = self.value_caster(self.value)
        else:
            self.casted_value = self.value_caster(self.value, date_format).format("YYYY-MM-DD")
        
        # Set up the link targets
        if "value_target" in self.data:
            targets = self.data["value_target"]
            if isinstance(targets, pd.Series):
                targets = targets.values
            else:
                targets = [targets]
        else:
            targets = [resolve_target(self.data)]
        self.targets = targets

    # Values are specific: they must have matching name, type, value, AND links
    def in_db(self, return_if_found=False):
        kwargs = {"name__exact": self.id_field,
                  self.TYPE_FIELD_MAP[self.type] + "__value__exact": self.casted_value,
                  "value_type__exact": self.vtype}
        # This gets us all values of a certain name and type (parameter, measure, metadata)
        # which we can then check for 
        values = Value.objects.filter(**kwargs)
        if len(values) == 0:
            return False

        # First, we whittle it down to make sure it has the fields we're explicitly looking for 
        for link_field in self.targets:
            if link_field == "extra_step":
                link_field = "step_id"
            model_name = link_field.split("_")[0]
            link_data = self.data[link_field]
            if isinstance(link_data, pd.Series):
                _id_list = link_data.values
            else:
                _id_list = [link_data]
            values = values.annotate(count=Count(plural_mapper[model_name])).filter(count=len(_id_list))
            if len(values) == 0:
                return False

            for _id in _id_list:
                vldtr = validator_mapper[model_name](pd.Series({link_field: _id}))
                obj = vldtr.fetch()
                kwargs = {plural_mapper[model_name]: obj}
                values = values.filter(**kwargs)
                if len(values) == 0:
                    return False
        # Next, we have to make sure it doesn't have any links to any other fields
        for field in linkable_fields:
            if field not in self.targets:
                #Check to make sure that nothing exists in each of these
                kwargs = {plural_mapper[model_name]: None}
                values = values.filter(**kwargs) 
        if return_if_found:
            return values
        else:
            return True 
        
    def validate(self):
        #Must raise an exception if failure to add to database
        #Only real requirement is that the linked objects exist
        for link_field in self.targets:
            if link_field == "extra_step":
                link_field = "step_id"
            model_name = link_field.split("_")[0]
            link_data = self.data[link_field]
            if isinstance(link_data, pd.Series):
                _id_list = link_data.values
            else:
                _id_list = [link_data]
            for _id in _id_list:
                vldtr = validator_mapper[model_name](pd.Series({link_field: _id}))
                obj = vldtr.validate()
        return True 
           
    def fetch(self):
        #Scenarios: in database, but not linked to the proper thing (false)
        # in database, and linked (true)
        # not in database (false)
        values = self.in_db(return_if_found=True)
        if values is False:
            raise Value.DoesNotExist
        return values

    def save(self):
        # First look to see if a Value with the same content exists, and we link that instead of making a new one
        # If Value does not exist, make the appropriate *Val and Value
        # Find each of the linkable items and add the value to its value_field, making sure that it's the right kind for that linkable
        permitted_types = {'parameter': ['result','step','process','analysis'],
                           'metadata': ['result','analysis', 'step', 'process', 'investigation','sample', 'feature'],
                           'measure': ['result','analysis','investigation','sample', 'feature']}
        try:
            values = self.fetch()
        except Value.DoesNotExist:
            values = []
        except:
            raise
  
        if len(values) == 0:
            val = self.TYPE_MODEL_MAP[self.type](value=self.casted_value)
            val.save()
            value = Value(content_object=val, name=self.id_field, value_type=self.vtype)
            value.save()
            # Make sure it's an object that can/should be linked to this value type

    def infer_type(self, date_format):
        found_types = list(set([x.content_type.model
            for x in Value.objects.filter(name__exact=self.name,
                                          value_type__exact=self.vtype)]))
        if len(found_types) > 1:
            raise DuplicateTypeError("Two types found for value name %s of \
                                      type %s" % (self.id_field, self.vtype))
        elif len(found_types) == 1:
            return found_types[0]
        else:
            strvalue = str(self.value)
            try:
                arrow.get(strvalue, self.date_format)
                return "datetimeval"
            except arrow.parser.ParserError:
                pass
            try:
                uuid.UUID(strvalue)
                return "resultval"
            except ValueError:
                pass
            try:
                int(strvalue)
                return "intval"
            except ValueError:
                pass
            try:
                float(strvalue)
                return "floatval"
            except ValueError:
                pass
            # Default value
            return "strval"

Validators = [InvestigationValidator, 
              ProcessValidator,
              StepValidator,
              SampleValidator,
              AnalysisValidator,
              ResultValidator,
              ValueValidator]


validator_mapper = {"investigation": InvestigationValidator,
                    "sample": SampleValidator,
                    "process": ProcessValidator,
                    "step": StepValidator,
                    "analysis": AnalysisValidator,
                    "result": ResultValidator,
                    "feature": FeatureValidator
                    }

def resolve_input_row(row):
    primary_target = resolve_target(row)
    validator = validator_mapper[primary_target.split("_")[0]](data=row)
    #If there are any pre-requisites from the primary target, it'll
    # attempt to validate and save them
    try:
        validator.validate()
        validator.save()
    except Exception as e:
        raise e

    for field, datum in row.iteritems():
        if (not pd.isna(datum)) & (field not in reserved_fields):
            data = row.drop(field)
            #If duplicates, focus on one
            data[field] = datum
            validator = ValueValidator(name=field, data=data)
            validator.validate()
            validator.save()

