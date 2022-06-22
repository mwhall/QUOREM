*****************
Development Guide
*****************

This section describes important files and useful functions for developing with QUOREM.

Development Resources
---------------------

QUOREM is built on powerful open-source tools and their documentation extends our own. Within QUOREM, Django's ORM can be used to perform complex data queries on data input from QIIME2, so these are particularly helpful sets of external documentation. QUOREM makes heavy use of Django's QuerySets.

:QIIME2: https://docs.qiime2.org/2022.2/
:Django: https://docs.djangoproject.com/en/4.0/
:django-filter: https://django-filter.readthedocs.io/en/stable/
:Plotly: https://plotly.com/python-api-reference/
:scikit-learn: https://scikit-learn.org/

Project Structure Walkthrough
-----------------------------

.. parsed-literal::
    QUOREM/
    |      manage.py
    |
    └───── quorem/
    |   |    settings.py
    |   |    urls.py
    |   |
    |   └── templates/
    |
    └───── db/
        |   artifacts.py
        |   spreadsheets.py
        |   tasks.py
        |   plot.py
        |   ml.py
        |
        └── models/
        |
        └── forms/
        |
        └── views/
    
Django projects are split into "apps", which are represented by subdirectories. QUOREM's apps are: `quorem`, `db`, `landingpage`, `accounts`. The `landingpage` and `accounts` are separated to enable easier customization of these aspects without affecting other areas.

quorem/
^^^^^^^

This app contains the main server configuration, including all settings and routing.

:`settings.py`: Django file that contains all server-specific configurations (including passwords!). Don't let secrets in this file get onto the internet.
:`urls.py`: Django file that maps server URLs onto Django Views (defined in the `db/` app principally).

db/
^^^

This app contains all of the database code.

:`artifacts.py`: Code for processing and parsing QIIME2 artifacts as server input.
:`spreadsheets.py`: Code for processing and parsing different spreadsheet formats as server input.
:`tasks.py`: Functions that are wrapped by Celery to be asynchronous tasks. These are typically functons that take too long in a web context, so the user launches the task and returns to get the result.
:`plot.py`: Plotting functions that support database visualization.
:`ml.py`: Machine learning functions for analyzing data in QUOREM.
:`models/`: This directory contains the [Django Models](https://docs.djangoproject.com/en/4.0/topics/db/models/) that define QUOREM's database schema. Each of the major `Object` concepts (Analysis, Process, Step, Result, Feature, Sample, Investigation) and their connections to one another are defined in these files. These Models all have useful methods that extend their utility and provide convenience when developing new features. Other concepts, such as the metadata Values and all of their valid data types are also defined in this directory.
:`forms/`: This directory contains [Django Forms](https://docs.djangoproject.com/en/4.0/topics/forms/) that define the widgets and GET/POST arguments for web pages that take in user input or other parameters.
:`views/`: This directory has the [Django Views](https://docs.djangoproject.com/en/4.0/topics/http/views/) that define each of QUOREM's web pages. These Views can be simple template rendering, or can take on a form that allows it to process input queries.

Walkthrough: Adding a new QUOREM webpage
----------------------------------------

In this walkthrough, we'll go through the process of adding a new web page with user input that redirects to a plot or some other HTML output.

Planning
^^^^^^^^

Start by developing the function that produces the output you want. For example, you might have a function that takes in an ASV table, a set of taxonomic classifications, and a query taxonomy string and produces some statistics on the distribution of taxa that match the query. Generally, widgets will take names or primary keys ("pk") of database objects to pass as arguments, so this is what your function should expect. 

Here is a function that takes in the primary key of a Result that contains a table/matrix, a Result that contains taxonomic classifications, and a query string to filter the results:

.. code-block:: python

    def sample_taxonomy_query(table_pk, taxonomy_pk, query_string):
        asv_table = Result.objects.get(pk=table_pk).get_value("asv_table")
        taxonomy = Result.objects.get(pk=taxonomy_pk)
        taxonomy = taxonomy.get_value(value_names=["taxonomic_classification"],
                                      additional_fields=["feature__name"])
        # Filter out the taxonomy table to only features matching the query
        taxonomy = taxonomy[taxonomy['value_data'].str.contains(query_string)]
        match_asvs = [x for x in taxonomy['features__name'] if x in asv_table.index ]
        filtered_table = asv_table.loc[match_asvs]
        n_not_found = sum(filtered_table.sum(axis=0) <= 0)
        n_found = asv_table.shape[1] - n_not_found
        output_string = "Found in %d samples (%.2f%% of total)" % (n_found, 
                                                                   100*float(n_found)/
                                                                   (n_found+n_not_found))
        return output_string

With this function designed, we can start to plan the web page that we will build to present this sophisticated analysis. We need to consider the URL we want, the widgets we want to use to collect our parameters/options, and how we want it all displayed.
