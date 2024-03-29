************
Installation
************

QUOREM is a series of servers (web, process, database), so installation is complex on existing systems. The web server is powered by Django, the process server Redis and Celery, and the database Postgresql. It can be run pretty effectively through the Docker container system, but a native install has some advantages. For trying out QUOREM or for machines that will only have local access (not on the web), the test server is sufficient. For servers with domain names pointing at them, an example of production deployment using Apache2 is provided.

To start, you must download a copy of the repository. You can do this with the ``git`` or ``gh`` utilities:

.. parsed-literal::
    git clone git@github.com:mwhall/QUOREM.git

or

.. parsed-literal::
    gh repo clone mwhall/QUOREM


Quickstart Development Mode with Docker
----------------------

Install the Docker engine using Docker's most up-to-date installation instructions: https://docs.docker.com/engine/install/

These instructions will only work to set up a server accessible by ``localhost`` or ``127.0.0.1`` from the Docker host machine. To deploy to an outside network, see the Production Deployment section below.

Make a copy of the `docker/example_secrets.env` file outside of the repository and **change the default passwords and secret key** and other settings, if desired:

.. parsed-literal::
    cp docker/example_secrets.env ~/quorem_secrets.env
    #Edit any desired settings in ~/quorem_secrets.env

Because we are setting up a database, cache, and web server as separate images, we'll be using ``docker compose`` from within the QUOREM project's root directory (where docker-compose.yml is located):

.. parsed-literal::
    sudo docker compose --env-file ~/quorem_secrets.env build

The build process installs a QIIME2 environment for QUOREM to utilize, so it can take 20 minutes to complete on the first build.

If using ``sudo`` with Docker, root needs access to the launch entrypoint for Django:

.. parsed-literal::
    chmod o+x docker/django_entrypoint.sh

To start the Docker up in the future use the ``up`` subcommand:

.. parsed-literal::
    sudo docker compose --env-file ~/quorem_secrets.env up

Note: The database files will be in /docker/persistence/postgresql/ but this folder **will be owned by root on your host system**. If you have Docker access but not root access on your host system, this could be a problem for you.

List the running containers with ``sudo docker ps``, and find the name of the container for quorem_django (likely quorem-django-1). You can attach to a bash shell the running container with ``sudo docker exec -it quorem-django-1 bash`` and after activating the QUOREM/QIIME2 conda environment with ``conda activate quorem``, you have full access to Django's management command line utilities through ``python manage.py``.

Native System Install
--------------

Install non-Conda dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A number of packages must be installed at the system level, which typically requires root access. On an Ubuntu server, you can install the required packages with ``apt``:

.. parsed-literal::
    sudo apt install tzdata gcc-multilib g++-multilib curl graphviz apache2 apache2-dev postgresql celery redis-server

Install miniconda
^^^^^^^^^^^^^^^^^

Miniconda is an environment manager that enables the creation of virtual environments. This keeps the many software dependencies of QUOREM safely isolated from your system's other versions. The gist is below butfull information is available at: https://docs.conda.io/en/latest/miniconda.html

.. parsed-literal::
   curl -LO "http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh"
   chmod u+x Miniconda3-latest-Linux-x86_64.sh
   ./Miniconda3-latest-Linux-x86_64.sh

After you have configured the installation using the interactive prompts, you will create and activate a conda environment for QUOREM with the appropriate Python version:

.. parsed-literal::
    conda update -y conda
    conda create --name quorem python=3.8.12
    conda activate quorem

Next, you must install QIIME2 in this conda environment:

.. parsed-literal::
    conda env update --file scripts/qiime2/qiime2-2022.8-py38-linux-conda.yml

Set up Postgresql Database
^^^^^^^^^^^^^^^^^^^^^^^^^^

Configure the Postgresql database. We do this by setting environment variables (see docker/example_secrets.env). You should keep your QUOREM deployment's environment file out of version control to avoid accidental pushing or overwriting.

.. parsed-literal::
    POSTGRES_USER=postgres
    POSTGRES_DB=quoremdb
    POSTGRES_PASSWORD=abcdefg12345

.. parsed-literal::
    sudo -u postgres bash -c "psql -c \"CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';\""
    sudo -u postgres createdb --owner=${POSTGRES_USER} ${POSTGRES_DB}

Django Configuration
^^^^^^^^^^^^^^^^^^^^

We need a secret key for our Django installation, and one can be generated from https://djecrety.ir/:

.. parsed-literal::
    DJANGO_SECRET_KEY="@v-n8hwx!@@jex(jqr-w^94^#_=%ub3ypd#*epx1&-rnv@@qj@"

Make sure to save these environment variables, as they must be set in the shell whenever QUOREM is run.
 
In the ``quorem/settings.py`` file, some default strings that are needed for the Docker install must be changed for a full system install:

Line 30: If your QUOREM server is using a qualified domain name or a static IP instead of ``localhost`` for remote access, either the domain or IP must be added to the ``ALLOWED_HOSTS`` list.

Line 102: ``CELERY_HOSTNAME`` must be set to ``127.0.0.1``

Line 148: ``HOST`` must be set to ``localhost`` for Postgresql.

Lines 181-186: (optional) Set up e-mail credentials to allow QUOREM to send password and account e-mails to users.

Finally, some Django commands must be run to set up the web server:

.. parsed-literal::
    python manage.py makemigrations
    python manage.py migrate
    python manage.py collectstatic
    python manage.py initialize

Once these have completed successfully, you must make a superuser account to approve any new users:

.. parsed-literal::
    python manage.py createsuperuser

You can now start the Django test server with:

.. parsed-literal::
    python manage.py runserver

This server works very well for local, single-user applications. Launching ``127.0.0.1`` in your web browser should bring up your new QUOREM instance. After signing up, be sure to log in with your superuser account and check the ``Has Access`` checkbox at ``127.0.0.1/admin/``.

Production Deployment
---------------------

In this section, we describe the general steps to tighten up configuration to allow secure remote access over the web to a QUOREM instance. We'll use the Apache2 webserver with the ``mod_wsgi`` plugin, a recommended approach for Django apps. This is a finnicky, often error-prone procedure. There are many ways to secure a production server, and this is one example. Report any issues or struggles to: https://github.com/mwhall/QUOREM/issues

First, in your QUOREM conda environment, ensure you have the ``mod_wsgi`` package.

.. parsed-literal::
    pip install mod_wsgi

It is _very_ important that you install this via ``pip`` in your conda environment. The ``mod_wsgi`` package used by Django and Apache must be the same version of Python as the other packages, which is typically not your system-level Python installation.

Find the location of your ``mod_wsgi`` compiled library with:

.. parsed-literal::
    mod_wsgi-express module-config

This will return two lines, but only the ``LoadModule`` line is needed. It should look something like (but may not be exactly):

.. parsed-literal::
    LoadModule wsgi_module "/home/quorem/miniconda3/envs/quorem/lib/python3.8/site-packages/mod_wsgi/server/mod_wsgi-py38.cpython-38-x86_64-linux-gnu.so"

Copy this line and with your favourite editor (and ``sudo``), edit the Apache2 configuration file at ``/etc/apache2/sites-available/000-default.conf``. The ``LoadModule`` line should go first, outside of any ``<VirtualHost>`` tags.

Inside the ``<VirtualHost>`` tag, set ``ServerName`` to your server's domain name, and ``DocumentRoot`` to the location of your QUOREM repository (e.g., ``/home/quorem/QUOREM/``).

Now it is time to run Certbot to get a Let's Encrypt certificate for SSL (secure web browsing) connections with your server. It will create a certificate and automatically modify your Apache2 configuration to forward your non-secure HTTP connections through SSL HTTPS encryption. *If you do not secure your server, all logins and data (including passwords!) sent and received will visible to those monitoring your traffic. ALWAYS SECURE YOUR TRAFFIC.* The instructions are available in full at: https://certbot.eff.org/instructions?ws=apache&os=ubuntufocal

This process, if successful, will have modified your ``000-default.conf`` and created a new ``000-default-le-ssl.conf`` file in the same ``/etc/apache2/sites-available`` directory. Once again with ``sudo``, edit this new file. Inside the ``<VirtualHost>`` tags, add the following lines, but be sure to *replace the directory names as appropriate* by replacing ``/home/quorem/QUOREM`` with the path to your QUOREM repository directory and ``/home/quorem/miniconda3/envs/quorem/`` to the path of the conda environment created earlier:

.. parsed-literal::
        WSGIProcessGroup quorem
        WSGIDaemonProcess quorem python-path=/home/quorem/QUOREM/ python-home=/home/quorem/miniconda3/envs/quorem/ user=quorem group=quorem
        WSGIScriptAlias / /home/quorem/QUOREM/quorem/wsgi.py application-group=%{GLOBAL} process-group=quorem

        Alias /static /home/quorem/QUOREM/staticfiles
        Alias /data /home/quorem/QUOREM/uploaddata
        <Directory /home/quorem/QUOREM/staticfiles>
            Require all granted
        </Directory>
        <Directory /home/quorem/QUOREM/uploaddata>
            Require all granted
        </Directory>
        <Directory /home/quorem/miniconda3/envs/quorem>
            Require all granted
        </Directory>

        <Directory /home/quorem/QUOREM/quorem>
            <Files wsgi.py>
                Require all granted
            </Files>
        </Directory>

Finally, restart your Apache2 server with this new configuration:

.. parsed-literal::
  sudo systemctl restart apache2

If there are any errors (especially if navigating to your domain produces "Internal Server Error"), you can start debugging by looking at the Apache2 logs at ``/var/log/apache2/error.log``.
