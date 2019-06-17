#!/bin/bash
echo -e "The script will create and configure a database.\n"
echo -e "This requires Anaconda ans PostgreSQL be installed.\n"
read -e -p "A virtual env will be created. Type the name of the virtual env you would like to use.`echo $'\n> '`" venv
read -p "Enter the name you would like to use for the database.`echo $'\n> '`" dbname
read -p "Enter the postgres username you would like to use.`echo $'\n> '`" pguname
read -s -p $"Type the password you will use for the database.`echo $'\n> '`" pswd1
read -s -p $"Please type the password again to confirm.`echo $'\n> '`" pswd2

if [ "$pswd1" != "$pswd2"]
then
	echo -e "Passwords don't match. Please try again.\n"
	exit 0
fi

conda create --name $venv python=3.7
conda activate $venv
pip install -r requirements.txt
sudo -u postgres bash -c "psql -c \"CREATE USER $pguname WITH PASSWORD '$pswd1';\""
sudo -u postgres createdb --owner=$pguname $dbname
python ./scripts/config.py $dbname $pguname $pswd1
python manage.py makemigrations && python manage.py migrate && python manage.py collectstatic

chmod 755 ./scripts/launchquorem.sh && sudo ln -s ./scripts/launchquorem.sh /usr/local/bin/launchdjango
chmod 755 ./scripts/runcelery.sh && sudo ln -s ./scripts/runcelery.sh /usr/local/bin/runcelery
chmod 755 ./scripts/resetdb.sh && sudo ln -s ./scripts/resetdb.sh /usr/local/bin/runcelery

touch credentials.txt
echo "Database name: $dbname" >> credentials.txt
echo "PostgreSQL user name: $pguname" >> credentials.txt
echo "Database password: $pswd1" >> credentials.txt
echo "conda environment: $venv" >> credentials.txt
echo "Installation complete. Type launchquorem to launch the app."
