#!/bin/bash
conda run -n quorem python manage.py makemigrations
conda run -n quorem python manage.py migrate
conda run -n quorem --no-capture-output python manage.py runserver 0.0.0.0:8000 &
conda run -n quorem --no-capture-output celery -A quorem worker --concurrency 1
