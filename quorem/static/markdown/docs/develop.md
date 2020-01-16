Title: Developing for QUOREM

This documentation is for those who want to:

 - Aid in the general development of QUOREM
 - Integrate/scrape a new QIIME2 result type into a QUOREM database
 - Integrate the results from another tool into a QUOREM database

[TOC]

## QUOREM Development

The central QUOREM GitHub is at: https://github.com/mwhall/QUOREM

More details on the architecture of QUOREM will be available here in the future.

## Scraping New QIIME2 Artifact Formats

QUOREM currently supports complete data input from the following artifacts formats: BIOMV210DirFmt, TSVTaxonomyDirectoryFormat, AlphaDiversityDirectoryFormat, DistanceMatrixDirectoryFormat, NewickDirectoryFormat, DADA2StatsDirFmt.

QUOREM aims to cache as much of the useful information in each QIIME2 filetype as is practical. However, you may have custom QIIME2 plugins, or new plugins that haven't been added to QUOREM by the main team yet. QUOREM will still archive it and scrape its metadata, but it will not have access to its primary data. In order to add new artifact types to QUOREM, the `db/artifacts.py` file has a `ArtifactDataScraper` class that must be subclassed out with a `qiime_format` attribute containing the name of the QIIME2 data type that this scraper handles. The `init` function is used to load the file from the .qza file, and `iter_data` and `iter_values` functions must be specified and must yield records in QUOREM's input format.

## Adding Results from Other Tools

For the moment, the best way to do this is to wrap any tool with [QIIME2](https://qiime2.org). QUOREM heavily leverages the metadata provenance that is tracked by all QIIME2 plugins. This vastly minimizes the effort for data input and validation, and is what allows QIIME results to be automatically sorted into the proper **Samples**, **Features**, **Steps** etc. without explicit user input. Without this metadata, the user must provide all of this information manually in a spreadsheet.
