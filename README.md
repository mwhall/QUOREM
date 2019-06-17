## Requirements
Python3 + Postgres + Redis + Celery

## Quick Start
0) Ensure you have anaconda/miniconda and PostgreSQL installed.

1) Clone or download this repo.

2) Execute install.sh from command line. You may need to change the permissions.
`chmod 755 install.sh`

3) Open a new tab in the terminal and activate the conda environment name which you provided to install.sh
`conda activate your_environment`

4)In the tab you ran install.sh, type:
`launchquorem`

5) In the second tab, type 
`runcelery`

6) Open a web browser and naviagte to localhost:8000. You should see the QUOR'em landing page.

If you forget any of the credentials you provided during installation, install.sh saves them all to a file called credentials.txt.

## For Developers
0) Install requirements:
`pip install -r requirements.txt`


1) Create postgres user:
`$ createuser -U postgres -P -s -e <your_new_username>`


2) Create a new - empty - database:
`$ createdb -U <username> <your_new_databasename>`


3) Edit the settings.py file:
Set your NAME, USER and PASSWORD for your database.


4) Make and migrate migrations:
`python manage.py makemigrations && python manage.py migrate`


5) Get staticfiles in order:
`python manage.py collectstatic`

6) Run the Celery task queue in one shell:
`celery -A quorem worker`

7) Run the application in another:
`python manage.py runserver`

## Troubleshooting
If you recieve an error during migration "cannot create extension pg_trgm", run the script
extenddb.sh with the usage:
$ extenddb.sh your_dbName.

To wipe your database and reset it, use the script resetdb.sh found in "scripts". If you used install.sh, you can simply type
`resetdb your_username your_database`

