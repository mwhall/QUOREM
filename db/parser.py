import arrow
import uuid
import pandas as pd
from django.core.exceptions import ObjectDoesNotExist
from .models import Replicate, Investigation, Sample, Process, ProcessCategory,\
                    Step, Value, Result, StrVal, IntVal, FloatVal, DatetimeVal, \
                    ResultVal, Analysis

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

    def __init__(self, data={}):
        self.data = data
        self.required_if_new = []
        self.optional_fields = []
        self.manytomany_fields = []
        self.jointly_unique = []
        self.django_mapping = {}

    def in_db(self):
        """Base Validator in database check
           id_field is the value in the id_field for this model
           But has to check all metadata, since some models have joint keys"""
        print("in_db")
        kwargs = {self.django_mapping[self.id_field] + "__exact": self.data[self.id_field]}
        for field1, field2 in self.jointly_unique:
            if (field1 == self.id_field):
                swap_field = field2
            elif (field2 == self.id_field):
                swap_field = field1
            if swap_field not in id_fields:
                kwargs[self.django_mapping[swap_field] + "__exact"] = self.data[swap_field]
            else:
                #We have to go grab the actual instance to pull the record out
                vldtr = validator_mapper[swap_field](data=self.data)
                try:
                    obj = vldtr.fetch()
                except:
                    return False
                kwargs[self.django_mapping[swap_field]] = obj
        try:
            print("in_db")
            print(kwargs)
            self.model.objects.get(**kwargs)
            return True
        except self.model.DoesNotExist:
            print("Didn't find it")
            return False

    def validate(self):
        """Base Validator validation routine
           Checks if the id field content is an integer and warns if it is
           If it is in the database, verify that all other fields are
           consistent with the database
           If it is not in the database, verify that the row contains
           all the other required information"""
        print("Validating")
        identifier = self.data[self.id_field]
        in_db = self.in_db()
        #Can't have integers as names to avoid confusion
        if (not in_db) & str(identifier).isdigit():
            raise InvalidNameError("To avoid confusion with database \
                                   indexes, %s names cannot be integers. \
                                   Add a prefix to the %s column." % \
                                   (self.model_name, self.id_field))
        #If not in database, make sure we have all the fields to save it
        if (not in_db):
            #If the investigation can't be found, we need to create it, and
            #that requires an institution and description
            missing_fields = [ x for x in self.required_if_new \
                                                   if x not in self.data ]
            if len(missing_fields) > 0:
                raise MissingColumnError("Columns " + \
                        ", ".join(missing_fields) + " missing and required")
        #if in database, make sure all their available data matches ours,
        #if not it's mistaken identity
        else:
            try:
                self.fetch(required_only=False)
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

    def fetch(self, required_only=False):
        """Does an exact fetch on all kwargs
           If kwargs[self.id_field] is an int then it queries that as pk"""
        if required_only:
            fields = self.required_if_new + [self.id_field]
        else:
            fields = self.required_if_new + self.optional_fields + [self.id_field]
        found_fields = [ x for x in fields if x in self.data ]
        kwargs = {}
        for field in found_fields:
            if field in id_fields:
                f_id = self.data[field]
                if field == self.id_field:
                    if str(f_id).isdigit():
                        name = int(f_id)
                        name_field = "pk"
                    else:
                        name = f_id
                        name_field = self.django_mapping[field] + "__exact"
                else:
                    vldtr = validator_mapper[field](data=self.data)
                    name = vldtr.fetch()
                    if str(f_id).isdigit():
                        name_field="pk"
                    else:
                        name_field = self.django_mapping[field]
                if field not in self.manytomany_fields:
                    kwargs[name_field] = name
            else:
                if field not in self.manytomany_fields:
                    kwargs[self.django_mapping[field] + "__exact"] =  self.data[field]
        #If fields are jointly unique, drag the other field into the query
        #even if it isn't in required
        print("Fetch")
        print(kwargs)
        # TODO: Should we validate m2m links here?
        return self.model.objects.get(**kwargs)

    def save(self):
        print("Saving")
        #Go through each field
        identifier = self.data[self.id_field]
        in_db = self.in_db()
        found_fields = [ x for x in
                  self.required_if_new + self.optional_fields if x in self.data ]
        kwargs = {}
        m2m_links = []
        for field in found_fields:
            #If x is an id field, then we have to fetch the actual object
            if field in id_fields:
                vldtr = validator_mapper[field](data=self.data)
                datum = vldtr.fetch()
            else:
                datum = self.data[field]
            if field in self.manytomany_fields:
                m2m_links.append((field, datum))
            else:
                kwargs[self.django_mapping[field]] = datum
        kwargs[self.django_mapping[self.id_field]] = identifier
        if not in_db:
            try:
                obj = self.model(**kwargs)
                obj.save()
                #Add the manytomany links to the model, which
                #can't be crammed into kwargs
            except:
                raise
        else:
            obj = self.fetch()
        for field, datum in m2m_links:
                getattr(obj, self.django_mapping[field]).add(datum)

class InvestigationValidator(Validator):
    model_name = "Investigation"
    model = Investigation
    value_field = "values"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "investigation_id"
        self.required_if_new = ["investigation_institution",
                                "investigation_description"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "institution",
                               self.required_if_new[1]: "description"}

class SampleValidator(Validator):
    model_name = "Sample"
    model = Sample
    value_field = "values"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "sample_id"
        self.required_if_new = ["investigation_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "investigation"}

class ReplicateValidator(Validator):
    model_name = "Replicate"
    model = Replicate
    value_field = "values"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "replicate_id"
        self.required_if_new = ["sample_id", "process_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "sample",
                               self.required_if_new[1]: "process"}

class ProcessCategoryValidator(Validator):
    model_name = "ProcessCategory"
    model = ProcessCategory

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "process_category_id"
        self.required_if_new = ["process_category_description"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "description"}

class ProcessValidator(Validator):
    model_name = "Process"
    model = Process
    value_field = "parameters"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "process_id"
        self.required_if_new = ["process_description", "process_citation", "process_category_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "description",
                               self.required_if_new[1]: "citation",
                               self.required_if_new[2]: "category"}

class StepValidator(Validator):
    model_name = "Step"
    model = Step
    value_field = "parameters"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "step_id"
        self.required_if_new = ["process_id",
                                "step_method",
                                "step_description"]
        self.manytomany_fields = ["process_id"]
        self.jointly_unique = [(self.id_field, self.required_if_new[1])]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "processes",
                               self.required_if_new[1]: "method",
                               self.required_if_new[2]: "description"}

class AnalysisValidator(Validator):
    model_name = "Analysis"
    model = Analysis
    value_field = "values"

    def __init__(self, date_format = "DD/MM/YYYY", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = "analysis_id"
        self.required_if_new = ["process_id"]
        self.manytomany_fields = ["extra_steps"]
        self.optional_fields = ["analysis_location", "analysis_date"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "process",
                               self.manytomany_fields[0]: "extra_steps",
                               self.optional_fields[0]: "location",
                               self.optional_fields[1]: "date"}
        # Transform the date to Django's default format
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #TODO: Generate a UUID if this is blank?
        self.id_field = "result_id"
        self.required_if_new = ["result_type",
                                "process_id",
                                "source_step_id",
                                "source_step_method",
                                "source_software"]
        self.manytomany_fields = ["replicate_id"]
        self.jointly_unique = [(self.required_if_new[2], self.required_if_new[3])]
        self.django_mapping = {self.id_field: "uuid",
                               self.required_if_new[0]: "type",
                               self.required_if_new[1]: "process",
                               self.required_if_new[2]: "source_step__name",
                               self.required_if_new[3]: "source_step__method",
                               self.manytomany_fields[0]: "replicates"}

    def fetch(self):
        return Result.objects.get(uuid=self.data["result_id"])

    def in_db(self):
        return Result.objects.filter(uuid=self.data["result_id"]).exists()

    def validate(self):
        print("Validating result")
        print(self.data)
        # First check that the process and source step exist
        print("Grabbing and validating process")
        process_vldtr = ProcessValidator(data=pd.Series({"process_id": self.data["process_id"]}))
        print("Fetching")
        process_vldtr.fetch()
        print("Grabbing and validating step")
        step_vldtr = StepValidator(pd.Series(data={"step_id": self.data["source_step_id"], "step_method": self.data["source_step_method"]}))
        step_vldtr.fetch()
        # Next, check that each replicate exists
        for field in self.data.index:
            if "replicate_id" in field:
                rep_vldtr = ReplicateValidator(data=pd.Series({"replicate_id": self.data[field]}))
                rep_vldtr.validate()
        return True

    def save(self):
        print("Saving result")
        process = ProcessValidator(data=pd.Series({"process_id": self.data["process_id"]})).fetch()
        source_step = StepValidator(data=pd.Series({"step_id": self.data["source_step_id"], 
                                     "step_method": self.data["source_step_method"]})).fetch()
        reps = Replicate.objects.filter(name__in=[self.data[x] for x in self.data.index if "replicate_id" in x])
        if not self.in_db():
            result = Result(uuid=self.data["result_id"], 
                            source_step = source_step,
                            source_software = self.data["source_software"],
                            type = self.data["result_type"],
                            process = process)
            result.save()
        else:
            # Make sure that the replicates are added
            result = self.fetch()
        for rep in reps:
            result.replicates.add(rep)



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
        self.vtype = self.data["value_type"]
        if self.vtype not in dict(Value.VALUE_TYPES):
            raise ValueError("vtype must be one of %s" % (str(
                                                          list(
                                                          dict(
                                        Value.VALUE_TYPES).keys())),))
        self.name = name
        self.value = self.data[name]
        print("Inferring value datatype")
        self.type = self.infer_type(date_format)
        print("Casting data with type %s" % (self.type,))
        self.value_caster = typecast(self.type)
        if self.type is not "datetimeval":
            self.casted_value = self.value_caster(self.value)
        else:
            self.casted_value = self.value_caster(self.value, date_format).format("YYYY-MM-DD")

    def fetch(self):
        print("Inferred type %s" % (self.type,))
        kwargs = {"name__exact": self.name,
                  self.TYPE_FIELD_MAP[self.type] + "__value__exact": self.casted_value,
                  "value_type__exact": self.vtype}
        return Value.objects.get(**kwargs)
        
    def validate(self):
        #Must raise an exception if failure to add to database
        #Only real requirement is that the linked objects exist
        for field in self.data.index:
            if field in id_fields:
                vldtr = validator_mapper[field](data=self.data)
                # Each linked item must exist
                if not vldtr.in_db():
                    raise NotFoundError("Value not inserted, %s with id %s not found" % (vldtr.model_name, self.data[field]))
            

    def in_db(self):
        #Scenarios: in database, but not linked to the proper thing (false)
        # in database, and linked (true)
        # not in database (false)
        try:
            kwargs = {"name__exact": self.name,
                      self.TYPE_FIELD_MAP[self.type] + "__value__exact": self.casted_value,
                      "value_type__exact": self.vtype}
            val = Value.objects.get(**kwargs)
            #All of the id fields in the row must exist and be linked
            for field in self.data.index:
                if field in id_fields:
                    vldtr = validator_mapper[field](data=self.data)
                    if vldtr.value_field is not None:
                        try:
                            obj = vldtr.fetch()
                            if val not in getattr(obj, vldtr.value_field):
                                return False
                        except:
                            return False
            return True
        except MultipleObjectsReturned:
            raise DuplicateEntryError("Two Value objects with the same name and value discovered. Inconsistent database.")
        except Value.DoesNotExist:
            return False
        except ObjectDoesNotExist:
            return False

    def resolve_target(self):
        #Rules:
        # - "investigation_id" only id -> investigation
        # - "investigation_id" and "sample_id" -> sample
        # - "investigation_id" and "sample_id" and "replicate_id" -> replicate
        # - "process_id" -> process
        # - "process_id" and "step_id" -> step
        # - "analysis_id" -> analysis
        # - "analysis_id" and "process_id" and "result_id" and "source_step_id" and "replicate_id" -> result
        precedence = ["result_id", "analysis_id", "step_id", "process_id", \
                      "replicate_id", "sample_id", "investigation_id"]
        for id_field in precedence:
            if id_field in self.data:
                print("Targeting %s" % (id_field,))
                return id_field


    def save(self):
        # First look to see if a Value with the same content exists, and we link that instead of making a new one
        # If Value does not exist, make the appropriate *Val and Value
        # Find each of the linkable items and add the value to its value_field, making sure that it's the right kind for that linkable
        permitted_types = {'PA': ['result','step','process','analysis'],
                           'MD': ['result','analysis','investigation','sample','replicate'],
                           'ME': ['result','analysis','investigation','sample','replicate']}
        try:
            value = self.fetch()
        except Value.DoesNotExist:
            print("Inferred type %s" % (self.type,))
            val = self.TYPE_MODEL_MAP[self.type](value=self.casted_value)
            val.save()
            value = Value(content_object=val, name=self.name, value_type=self.vtype)
            value.save()
        except:
            raise
            # Make sure it's an object that can/should be linked to this value type
        print("Got value, linking")
        target_field = self.resolve_target()
        for field in self.data.index:
            #This covers replicate_id, replicate_id.1, replicate_id.2 etc.
            if (field in target_field) and (field.split("_")[0] in permitted_types[self.vtype]):
                print("Grabbing object %s" % (field,))
                vldtr = validator_mapper[field.split(".")[0]](data=self.data)
                # Swap the alternate out if necessary
                vldtr.data[vldtr.id_field] = self.data[field]
                #Make the link
                print(vldtr.value_field)
                if vldtr.value_field is not None:
                    print("Fetching")
                    obj = vldtr.fetch()
                    print("Linking")
                    getattr(obj, vldtr.value_field).add(value)
                    print("Linked")


    def infer_type(self, date_format):
        found_types = list(set([x.content_type.model 
            for x in Value.objects.filter(name__exact=self.name,
                                          value_type__exact=self.vtype)]))
        if len(found_types) > 1:
            raise DuplicateTypeError("Two types found for value name %s of \
                                      type %s" % (self.name, self.vtype))
        elif len(found_types) == 1:
            print("Found existing value with type %s" % (found_types[0]))
            return found_types[0]
        else:
            strvalue = str(self.value)
            try:
                arrow.get(strvalue, date_format)
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
              ReplicateValidator,
              ProcessCategoryValidator,
              ProcessValidator,
              StepValidator,
              SampleValidator,
              ValueValidator]

id_fields = ["investigation_id", "process_category_id", "process_id", \
             "step_id", "sample_id", "replicate_id", "analysis_id", "result_id"]

reserved_fields = id_fields + ["investigation_description", \
                               "investigation_citation", \
                               "investigation_institution", \
                               "process_category_description", \
                               "process_description", "process_citation", \
                               "step_method", \
                               "step_action", \
                               "step_description", \
                               "result_type", \
                               "analysis_location", \
                               "analysis_date", \
                               "value_type", \
                               # Not a primary id field, only used for Result, which is in a custom class
                               "source_step_id", \
                               "source_step_method", \
                               "source_software"]

validator_mapper = {"investigation_id": InvestigationValidator,
                    "sample_id": SampleValidator,
                    "replicate_id": ReplicateValidator,
                    "process_category_id": ProcessCategoryValidator,
                    "process_id": ProcessValidator,
                    "step_id": StepValidator,
                    "analysis_id": AnalysisValidator,
                    "result_id": ResultValidator,
                    }


def resolve_input_row(row):
    #row: an object s.t. row['sample_id'] gets a single sample id
    # from e.g. a spreadsheet
    #We resolve the objects in order that they would need to be created if a
    # record were to be inserted from scratch, and if every detail were to be
    # included in a single line for some insane reason
    #This progressive validation ensures that absolutely everything present in
    #the Spreadsheet is compatible with the database
    #It will throw an error if:
    # - An _id column exists in the input, but not in the database, and other required data is missing (MissingColumnError)
    # - An _id column exists in the input, but not in the database, and is an integer (InvalidNameError; id is either pk or name, so we don't want ints as names to cause a conflict here)
    # - An _id column exists in the input, and one of its required fields is also in the input, but the contents differ with what's in the database
    # - If none of these conditions hold, then either 1) it's in the database, or 2) we can put it in there
    print("Saving objects...")
    for field in id_fields:
        if field in row:
            validator = validator_mapper[field](data=row)
            try:
                print("Validating and saving field %s"%(field,)) 
                validator.validate()
                print("Saving")
                validator.save()
                print("saved")
            except Exception as e:
                raise e
    print("Saving values...")
    for field in row.index:
        id_substr = False
        if (not pd.isna(row[field])) & (field not in reserved_fields):
            for id_field in id_fields:
                if field in id_field:
                    id_substr = True
            if not id_substr:
                print("Value field: %s" % (field,))
                print("Value value: %s" % (row[field],))
                # It's a generic Value field
                validator = ValueValidator(name=field, data=row)
                print("Validating")
                validator.validate()
                print("Saving")
                validator.save()

