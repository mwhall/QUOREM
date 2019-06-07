from .models import BiologicalReplicate, BiologicalReplicateProtocol, \
                    Investigation, Sample, SampleMetadata, BiologicalReplicateMetadata, \
                    ProtocolParameterDeviation, ProtocolStep, ProtocolStepParameter, \
                    ProtocolStepParameterDeviation

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

class NotFoundError(Exception):
    pass

#Generic Validator functions go here
class Validator():
    def __init__(self, data={}):
        self.data = data
        self.required_if_new = []
        self.optional_fields = []
        self.django_mapping = {}

    def in_db(self):
        """Base Validator in database check
           id_field is the value in the id_field for this model
           But has to check all metadata, since some models have joint keys"""
        identifier = self.data[self.id_field]
        try:
            self.fetch(required_only=True)
            return True
        except self.model.DoesNotExist:
            return False

    def validate(self):
        """Base Validator validation routine
           Checks if the id field content is an integer and warns if it is
           If it is in the database, verify that all other fields are
           consistent with the database
           If it is not in the database, verify that the row contains
           all the other required information"""
        identifier = self.data[self.id_field]
        in_db = self.in_db()
        #Can't have integers as names to avoid confusion
        if (not in_db) & identifier.isdigit():
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
            #TODO This raises mistakenly on ProtocolStepParameters when there are parameters with the same name, but derive from different protocol_steps
            #We need to be able to handle cases where the id_field is possibly jointly unique on another field
            try:
                self.fetch(required_only=False)
            except self.model.DoesNotExist:
                raise InconsistentWithDatabaseError("%s id %s found in database, \
                    but other %s fields do not exactly match database values.\
                    Value: %s. If you know the id is correct, remove the other %s fields\
                    and it will submit to that %s." % (self.model_name,
                                                       self.id_field,
                                                       self.model_name,
                                                       self.data[id_field],
                                                       self.model_name,
                                                       self.model_name))
        return True

    def fetch(self, required_only=False):
        """Does an exact fetch on all kwargs
           If kwargs[self.id_field] is an int then it queries that as pk"""
        identifier = self.data[self.id_field]
        if required_only:
            fields = self.required_if_new
        else:
            fields = self.required_if_new + self.optional_fields
        found_fields = [ x for x in fields if x in self.data ]
        kwargs = { self.django_mapping[x] + "__exact": self.data[x] for x in found_fields if x not in id_fields }
        if identifier.isdigit():
            name = int(identifier)
            name_field = "pk"
        else:
            name = self.data[self.id_field]
            name_field = self.django_mapping[self.id_field] + "__exact"
        kwargs[name_field] = name
        return self.model.objects.get(**kwargs)

    def save(self):
        #Go through each field
        identifier = self.data[self.id_field]
        in_db = self.in_db()
        if (not in_db):
            found_fields = [ x for x in
                  self.required_if_new + self.optional_fields if x in self.data ]
            kwargs = {}
            for field in found_fields:
                #If x is an id field, then we have to fetch the actual object
                if field in id_fields:
                    vldtr = validator_mapper[field]({field: self.data[field]})
                    mdl = vldtr.model
                    datum = mdl.objects.get(**{vldtr.django_mapping[field] + "__exact": self.data[field]})
                else:
                    datum = self.data[field]
                kwargs[self.django_mapping[field]] = datum
            kwargs[self.django_mapping[self.id_field]] = identifier
            try:
                new_model = self.model(**kwargs)
                new_model.save()
            except:
                raise

class InvestigationValidator(Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = "Investigation"
        self.model = Investigation
        self.id_field = "investigation_id"
        self.required_if_new = ["investigation_institution",
                                "investigation_description"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "institution",
                               self.required_if_new[1]: "description"}

class SampleValidator(Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = "Sample"
        self.model = Sample
        self.id_field = "sample_id"
        self.required_if_new = ["investigation_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "investigation"}

class BiologicalReplicateValidator(Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = "BiologicalReplicate"
        self.model = BiologicalReplicate
        self.id_field = "replicate_id"
        self.required_if_new = ["sample_id", "protocol_id"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "sample",
                               self.required_if_new[1]: "biological_replicate_protocol"}

class BiologicalReplicateProtocolValidator(Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = "BiologicalReplicateProtocol"
        self.model = BiologicalReplicateProtocol
        self.id_field = "protocol_id"
        self.required_if_new = ["protocol_description", "protocol_citation"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "description",
                               self.required_if_new[1]: "citation"}

class ProtocolStepValidator(Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = "ProtocolStep"
        self.model = ProtocolStep
        self.id_field = "protocol_step_id"
        self.required_if_new = ["protocol_step_method"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "method"}

class ProtocolStepParameterValidator(Validator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_name = "ProtocolStepParameter"
        self.model = ProtocolStepParameter
        self.id_field = "protocol_step_parameter_id"
        self.required_if_new = ["protocol_step_id",
                                "protocol_step_parameter_value"]
        self.optional_fields = ["protocol_step_parameter_description"]
        self.django_mapping = {self.id_field: "name",
                               self.required_if_new[0]: "protocol_step",
                               self.required_if_new[1]: "value",
                               self.optional_fields[0]: "description"}


#### These are not as straightforward, since they are jointly unique on some
#### fields and have no simple primary key

class ProtocolDeviationValidator(Validator):
    def __init__(self, *args, **kwargs):
        self.model_name = "ProtocolStepParameterDeviation"
        self.model = ProtocolStepParameterDeviation
        self.id_field = None
        self.required_if_new = []
        self.django_mapping = {}

class SampleMetadataValidator(Validator):
    model_name = "SampleMetadata"
    model = SampleMetadata

    def __init__(self, key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #In the case of SampleMetadata, id_field is the metadata field name
        self.id_field = key
        self.value_field = self.data[self.id_field]
        self.required_if_new = ["sample_id"]
        self.django_mapping = {self.id_field: "key",
                               self.required_if_new[0]: "sample"}

    def in_db(self):
        identifier = self.data[self.id_field]
        sample_identifier = self.data["sample_id"]
        try:
            #This will need to check for index pk TODO
            samp = Sample.objects.get(name__exact=sample_identifier)
            kwargs = {"key__exact": self.id_field,
                      "value__exact": self.value_field,
                      "sample": samp}
            obj = self.model.objects.get(**kwargs)
            return True
        except Sample.DoesNotExist:
            raise NotFoundError("sample_id %s not found in database, failed to find associated metadata entry")
            return False
        except self.model.DoesNotExist:
            return False


    def validate(self):
        #First, get the sample
        samp = Sample.objects.get(name__exact=self.data["sample_id"])
        #Check if in database
        try:
            self.model.objects.get(sample = samp,
                                   key = self.id_field,
                                   value = self.value_field)
        except self.model.DoesNotExist:
            #Not in database, check if inconsistsent, or nonexistent
            try:
                self.model.objects.get(sample = samp,
                                       key = self.id_field)
            except self.model.DoesNotExist:
                #Cleared for writing
                return True
            raise InconsistentWithDatabaseError("SampleMetadata is \
                        inconsistent with the database for field %s. Not \
                        overwriting." % (self.id_field,))
        return True

    def save(self):
        if (not self.in_db()):
            #First, get the sample
            samp = Sample.objects.get(name__exact=self.data["sample_id"])
            mdl = self.model(sample = samp,
                             key = self.id_field,
                             value = self.value_field)
            mdl.save()



class BiologicalReplicateMetadataValidator(Validator):
    model_name = "BiologicalReplicateMetadata"
    model = BiologicalReplicateMetadata

    def __init__(self, key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id_field = key
        self.value_field = self.data[self.id_field]
        self.required_if_new = ["replicate_id"]
        self.django_mapping = {self.id_field: "key",
                               self.required_if_new[0]: "biological_replicate"}

    def in_db(self):
        identifier = self.data[self.id_field]
        rep_identifier = self.data["replicate_id"]
        try:
            #This will need to check for index pk TODO
            biorep = BiologicalReplicate.objects.get(name__exact=rep_identifier)
            kwargs = {"key__exact": self.id_field,
                      "value__exact": self.value_field,
                      "biological_replicate": biorep}
            obj = self.model.objects.get(**kwargs)
            return True
        except BiologicalReplicate.DoesNotExist:
            raise NotFoundError("replicate_id %s not found in database, failed to find associated metadata entry")
            return False
        except self.model.DoesNotExist:
            return False

    def validate(self):
        #First, get the sample
        biorep = BiologicalReplicate.objects.get(name__exact=self.data["replicate_id"])
        #Check if in database
        try:
            self.model.objects.get(biological_replicate = biorep,
                                   key = self.id_field,
                                   value = self.value_field)
        except self.model.DoesNotExist:
            #Not in database, check if inconsistsent, or nonexistent
            try:
                self.model.objects.get(biological_replicate = biorep,
                                       key = self.id_field)
            except self.model.DoesNotExist:
                #Cleared for writing
                return True
            raise InconsistentWithDatabaseError("BiologicalReplicateMetadata is \
                        inconsistent with the database for field %s. Not \
                        overwriting." % (self.id_field,))
        return True

    def save(self):
        #First, get the replicate
        if (not self.in_db()):
            biorep = BiologicalReplicate.objects.get(name__exact=self.data["replicate_id"])
            mdl = self.model(biological_replicate = biorep,
                             key = self.id_field,
                             value = self.value_field)
            mdl.save()



Validators = [InvestigationValidator, BiologicalReplicateValidator,
              BiologicalReplicateMetadataValidator,
              BiologicalReplicateProtocolValidator,
              ProtocolStepValidator,
              ProtocolStepParameterValidator,
              SampleValidator, SampleMetadataValidator,
              ProtocolDeviationValidator]

id_fields = ["investigation_id", "protocol_id", "protocol_step_id",
             "protocol_step_parameter_id", "sample_id", "replicate_id"]
reserved_fields = id_fields + ["investigation_description", \
                               "investigation_citation", \
                               "investigation_institution", \
                               "protocol_description", "protocol_citation", \
                               "protocol_step_name", "protocol_step_method", \
                               "protocol_step_parameter_name", \
                               "protocol_step_parameter_value", \
                               "protocol_step_parameter_description", \
                               "deviated_step_name", "deviated_parameter_name",\
                               "deviated_value"]
validator_mapper = {"investigation_id": InvestigationValidator,
                    "sample_id": SampleValidator,
                    "replicate_id": BiologicalReplicateValidator,
                    "protocol_id": BiologicalReplicateProtocolValidator,
                    "protocol_step_id": ProtocolStepValidator,
                    "protocol_step_parameter_id": ProtocolStepParameterValidator}


def resolve_input_row(row):
    #row: an object s.t. row['sample_id'] gets a single sample id
    # from e.g. a spreadsheet
    #We resolve the objects in order that they would need to be created if a
    # record were to be inserted from scratch, and if every detail were to be
    # included in a single line for some insane reason
    #Once all objects in the row are resolved and found not to conflict, then we will save all objects in the row
    validators = []
    #This progressive validation ensures that absolutely everything present in
    #the Spreadsheet is compatible with the database
    #It will throw an error if:
    # - An _id column exists in the input, but not in the database, and other required data is missing (MissingColumnError)
    # - An _id column exists in the input, but not in the database, and is an integer (InvalidNameError; id is either pk or name, so we don't want ints as names to cause a conflict here)
    # - An _id column exists in the input, and one of its required fields is also in the input, but the contents differ with what's in the database
    # - If none of these conditions hold, then either 1) it's in the database, or 2) we can put it in there
    for field in id_fields:
        if field in row:
            validator = validator_mapper[field](data=row)
            try:
                validator.validate()
                validators.append(validator)
            except Exception as e:
                raise e
    metadata_validators = []
    # - Once we've shown that the whole row is consistent, we can save it to the database
    if ("replicate_id" in row) and ("sample_id" in row):
        #We need to validate SampleMetadata and BiologicalReplicate
        print("rep: ", row['replicate_id'])
        print("samp: ", row["sample_id"])
        metadata_validators = [SampleMetadataValidator, BiologicalReplicateMetadataValidator]
    elif "replicate_id" in row:
        print("2")
        metadata_validators = [BiologicalReplicateMetadataValidator]
    elif "sample_id" in row:
        print("3")
        metadata_validators = [SampleMetadataValidator]
    for validator in validators:
        validator.save()

    invs_seen= {}
    samples_seen = {}


    for validator in metadata_validators:
        for field in row.index:
            if field not in reserved_fields:
                vldr = validator(field, data=row)
                vldr.validate()
                vldr.save()
