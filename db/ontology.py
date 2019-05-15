#This document contains the code for linking the QUOREM data models
# to an ontology file for validating input into the database

# Change Step to process

#This code is currently stubs

def get_sample_metadata_details(ontology):
    """Returns a list of dicts of the metadata categories that are
    valid for Sample objects. e.g. {"name": "pH", "type": "float", "mandatory": "no"}"""
    pass

def get_replicate_metadata_details(ontology):
    """Returns a list of dicts of the metadata categories that are
    valid for BiologicalReplicate objects. e.g., {"name": "date_processed", "type": "datetime", "mandatory": "no"}"""
    pass

def get_wetlab_protocol_options(ontology):
    """Returns a list of dicts of the wetlab protocol steps, their methods, and 
    their parameters. e.g., {"step": 
                               {"name": "amplification", 
                                "methods": [
                                     {"name": "pcr", "parameters": [
                                       {"name": "ncycles", "default_value": 5}] 
                                     }]}}"""
    pass

def get_computational_protocol_options(ontology):
    """Returns a list of dicts of the computational protocol steps, their methods, and 
    their parameters. e.g., {"step": 
                               {"name": "amplification", 
                                "methods": [
                                     {"name": "pcr", "parameters": [
                                       {"name": "ncycles", "default_value": 5}] 
                                     }]}}"""
    pass

