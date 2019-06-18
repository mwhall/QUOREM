## Requirements
Python3 + Postgres + Redis + Celery

Postgres:
https://www.postgresql.org/download/

Redis:
https://redis.io/topics/quickstart

## Quick Install
Quick install requires anaconda or miniconda. 

0) Make sure you have anaconda/miniconda, postgres, and redis installed.

1) Download or clone this repository. 

2) Navigate to the cloned folder and run install.sh. You may need to change the permissons.

`$ chmod 755 install.sh`
`$ ./install.sh`

3) Follow the directions on screen. Don't worry about forgetting your credentials; the install script 	
   will create a text file saving them.

4) During installation you will be asked to choose a name for a virtual environment. 
   To start QUOREM, open two console tabs. In the first, type:

`$ launchquorem`
   In the second, type:
`$ runcelery`
   Then, open your web browser and navigate to localhost:8000. QUOREM should be functioning there.

5) To wipe your database, use the resetdb utility. Simply type:
`$ resetdb yourPostgresUsername yourDatabaseName`

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
$ ./extenddb.sh your_dbName.

Utility scripts will not be configured properly without using install.sh. If you chose to manually install, you will have to reconfigure them to work on your system.

