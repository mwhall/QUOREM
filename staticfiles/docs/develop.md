Title: Developing for QUOR'em
# QUOR'em Developer Documentation

This documentation is for those who want to:

 - Aid in the general development of QUOR'em
 - Create a custom Wiki Report for their instance
 - Integrate/scrape a new QIIME2 result type into a QUOR'em database
 - Integrate the results from another tool into a QUOR'em database

## General Development

Our GitHub is at: https://github.com/mwhall/QUOREM

Have a feature suggestion? Bug report? Have you fixed something? If you're maintaining a fork of QUOR'em, you can always perform a pull request and merge your code for everyone to use!

If you're interested in the Django setup, this information is on the [Django](wiki:/django) page. The database schema is described on the [Schema](wiki:/schema) page.

## Creating Automated Wiki Reports

Task level: System Administrator
Skills required: Python coding

See the [Reports](wiki:/reports) page for detailed information. Adding new reports to a QUOR'em instance involves subclassing the `WikiReport` class in `quorem/wiki_reports.py` and defining valid slugs and a function that parses the slug and returns a valid markdown report to be inserted in the wiki. Once this subclass exists, the report can be added to save triggers, or can be manually run by the administrator with the `python manage.py refreshwiki` command.

## Scraping New QIIME2 Types

Task level: System Administrator
Skills required: Pythong coding

QUOR'em aims to cache as much of the useful information in each QIIME2 filetype as is practical. However, you may have custom QIIME2 plugins, or new plugins that haven't been adding to QUOR'em by the main team yet. In this case, the QIIME type must be added to the functions in `db/registered_artifacts.py`. More details can be found on the [QIIME2](wiki:/QIIME2) page.

## Adding Results from Other Tools

For the moment, the best way to do this is to wrap any tool with [QIIME2](https://qiime2.org). QUOR'em heavily leverages the metadata provenance that is tracked by all QIIME2 plugins. This vastly minimizes the effort for data input and validation, and is what allows QIIME results to be automatically sorted into the proper samples, replicates, pipeline, etc. without explicit user input. Without this metadata, the user must provide all of this information. It may make sense to add a generic result to Samples and BiologicalReplicates, but it may also suffice to input other tool results in a spreadsheet as SampleMetadata or BioligicalReplicateMetadata.
