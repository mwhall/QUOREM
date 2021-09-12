# Overview of QUOREM

QUOREM is an open-source web server for storing microbial ecology data. The primary goal of the QUOREM project is to make organizing and analyzing microbial ecology data easier for small research groups.


QUOREM runs on a computer running Linux and Python, and can be run as a development server and accessed locally, or hosted on a network-accessible computer with Apache to provide access to provide more robust access to distributed groups. Source code is available on GitHub at: https://github.com/mwhall/QUOREM

## QUOREM Features

- Drag-and-drop upload of spreadsheets and QIIME2 artifact files
- Stores data about ASVs, OTUs, and taxonomic groups:
  - Taxonomic classifications
  - Abundances
  - Related biological sequences
  - Trees
- Keeps your samples and their metadata organized
- Download stored artifacts and metadata in convenient formats to take your analysis further

## Objects

On a QUOREM server, data are organized as objects that are accessed through an [Object-relational mapping (ORM)](https://en.wikipedia.org/wiki/Object%E2%80%93relational_mapping) provided by the [Django project](https://www.djangoproject.com/).

Sample
: A sample is typically biological material taken from an environment, or something derived from a sample.
  For example, soil taken from a forest may be a sample, while replicates made or sequencing runs based on that material may be derived samples.

Feature
: A feature is anything that has measures that are tracked across samples.
  More specific examples may be amplicon sequence variants (ASVs), operational taxonomic units (OTUs), functional genes, or metabolites.

Step
: A step represents a transformation on either a physical sample or a data file.

Process
: A process is a set of linked steps and parameters.
  For example, a set of QIIME2 commands would be a process.

Result
: A result is a set of values from a given computational or wet-lab step.
  For example, a QIIME2 artifact is considered a result and contains many values that are imported to QUOREM, such as abundances or taxonomic classifications.

Analysis
: An analysis is any time a process is run, i.e., it is a specific instantiation of a set of steps.
  For example, running a denoising pipeline would be one analysis, while running an OTU clustering pipeline on the same data would be a second analysis.

Investigation
: An investigation is the motivation for an analysis.

Value
: A value is a piece of data that can be attached to any of the other objects, including multiple types and multiple of the same type.
  For example, a taxonomic classification is a piece of data that is attached to a feature and a result.


Each of these objects are connected to one another through the ORM, allowing for data from one object to be retrieved through other objects, as long as those objects are connected.
