#!/bin/bash
if [ $# -lt 1 ]; then
	echo "Usge: extenddb your_db_name"
	exit
fi
sudo -u postgres psql $1 -c "CREATE EXTENSION pg_trgm"
