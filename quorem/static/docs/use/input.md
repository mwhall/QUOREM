# Inputting Data to QUOR'em

## Input File Types

Currently, QUOR'em accepts exactly two types of data files: 

 - TSV/CSV spreadsheets for registering Investigations, Samples, Replicates, Protocols, Pipelines, and Metadata
 - QZA/QZV files from QIIME2 analyses

## Where to Input Data

All data can be uploaded from the [upload page](/upload/new) or input at the respective create URL. Currently, QUOR'em accepts two types of upload file input: TSV/CSV spreadsheets, and QIIME2 results (QZA/QZV).

**Note: Data can be submitted in bulk, as long as the information in the spreadsheet is consistent with the database**
**i.e., Investigations, Samples, and Biological Replicates can be submitted on the same spreadsheet**

### Investigation example:

investigation_id|investigation_description|investigation_institution
----------------|-------------------------|-----------------
Sequence the Kraken! | An amplicon survey of suspected sea monster habitats in Nova Scotia | Dalhousie University

`investigation_id` if the investigation is already in the database, this can be either the integer index of the investigation from the URL of many of the webpages, or the name (case-sensitive, exact match). If the investigation is new, this must be a name that is not already in the database.

### Sample example:

investigation_id|sample_id|...
----------------|---------|---
Sequence the Kraken!|Northumberland Strait|...

`investigation_id` can be either the integer index of the investigation from the URL of many of the webpages, or the name (case-sensitive, exact match).
`sample_id` If the sample is already in the database, this can be either the integer index of the sample from the URL of many of the webpages, or the name (case-sensitive, exact match). If the sample is new, this must be a name that is not already in the database.
`...` can be any non-reserved column name. These values will be added to the database as SampleMetadata. For example, this is where you would put pH or Collection Date (but be sure to use consistent terms, in spelling and case!).

If you are only submitting a sample (and adding it to an existing investigation), an investigation identifier must be provided, but the institution and description may be left out of the sheet. They can be included, but they must match what is in the database exactly.

### Biological Replicate example:

sample_id|protocol_id|replicate_id|...
---------|-----------|------------|...
Northumberland Strait|Hall et al., 2019|NorthStrait 16S V6-V8|...
Kejimkujik|Hall et al., 2019|Keji 16S V6-V8|...

`sample_id` If the sample is already in the database, this can be either the integer index of the sample from the URL of many of the webpages, or the name (case-sensitive, exact match). If the sample is new, this must be a name that is not already in the database, and `investigation_id` must also be present in the sheet.
`protocol_id` This can be either the integer index of the protocol from the URL of many of the webpages, or the name (case-sensitive, exact match).
`...` can be any non-reserved column name. These values will be added to the database as BiologicalReplicateMetadata. For example, this is where you would put run quality or sequencing facility (but be sure to use consistent terms, in spelling and case!).

### Protocol example:

protocol_name|protocol_description|protocol_citation|protocol_step_name|protocol_step_method|protocol_step_method_description|protocol_step_parameter_name|protocol_step_parameter_value|protocol_step_parameter_description
-------------|--------------------|-----------------|------------------|--------------------|----------------------------|-----------------------------|-----------------------------------|---------------
16S V6-V8|A protocol for amplifying sea monster-specific taxa|Hall et al., 2019|amplification|Amplification of small amounts of DNA before sequencing|pcr|ncycles|10|Number of thermal cycles in the PCR amplification

### Pipeline example:

These can be produced automatically with the `q2_extractor` Python utility. Instructions to come.

### Protocol Deviation example:

If a Biological Replicate was performed, but the standard Protocol was deviated from in any of its **parameters**, then this difference must be input to the QUOR'em database:

replicate_id|deviated_step_name|deviated_step_method|deviated_step_parameter_name|deviated_value
------------|------------------|----------------------------|--------------|---------
Keji 16S V6-V8|amplification|pcr|ncycles|5
