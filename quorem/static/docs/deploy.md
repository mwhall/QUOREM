# Deploying QUOR'em

You can launch your own private instance of QUOR'em to keep all of your research group's data in one place. This is the guide for system administrators who wish to deploy their own instance of QUOR'em.

## Operating System

Unless otherwise stated, the instructions for this guide have been tested on Ubuntu 18.04 LTS. We are planning guides for setting up on common commercial compute solutions such as AWS, DigitalOcean, Heroku etc.

## Software Overview

### Web Front-End

The web front-end is powered by Django 2.2. Several Django libraries are included and required: [django-cors-headers](https://pypi.org/project/django-cors-headers/), [djk-jinja-knockout](https://github.com/Dmitri-Sintsov/django-jinja-knockout), [djk-bootstrap4](https://github.com/Dmitri-Sintsov/djk-bootstrap4), [django-wiki](https://github.com/django-wiki/django-wiki.git), (django-nyt)[https://github.com/django-wiki/django-nyt], (django-mptt)[https://github.com/django-mptt/django-mptt], (django-sekizai)[https://github.com/divio/django-sekizai], and (sorl-thumbnail)[https://github.com/jazzband/sorl-thumbnail].

Most of these libraries are installed with the `pip -r requirements.txt` command. django-wiki requires an unmerged pull request that provides support for Django 2.2. This is only temporary until this has been incorporated into django-wiki.

## Database Back-End

While this is highly configurable through Django, by default the data are stored in a PostgreSQL database. The connection information is stored in `quorem/settings.py`.

First, the `postgres` user must exist on your system. Next, create a user for QUOR'em to connect through `sudo -u postgres psql -c "CREATE USER username WITH PASSWORD password;\" where `username` and `password` are replaced with the username and password you desire for your database. Then create the database with the desired `dbname` with the command `postgres createdb --owner=username dbname`, using the `username` from the previous command. Finally, we have to extend the PostgreSQL database with the command `sudo -u postgres psql dbname -c "CREATE EXTENSION pg_trgm"`.

## Task Server

To avoid slowing down the main server thread, tasks such as input data validation, intensive searches, and plotting are farmed out to a (Celery)[https://docs.celeryproject.org/en/latest/index.html] task queue server. A redis server can be installed and used with Celery to execute the tasks. This is installed as a part of the `pip install -r requirements.txt` command. It's sufficient to have these running on the same machine for small servers. For larger servers, you may need to look at the Celery documentation to point the task queue at a remote server.

## Python Libraries

We also use several Python libraries in order to provide additional functionality to the application. This includes plotly, ...

# Step-By-Step Deployment

Coming soon...
