#!/bin/bash
if [ $# -lt 2 ]; then
	echo "Usage: resetdb.sh owner dbname"
	exit
fi
sudo -u postgres dropdb $2 && sudo -u postgres createdb --owner=$1 $2 && sudo -u postgres psql $2 -c "CREATE EXTENSION pg_trgm"
find . -path "*/migrations/*.pyc"  -delete
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic
python manage.py initialize
