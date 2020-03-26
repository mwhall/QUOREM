#!/bin/bash
celery -A quorem worker --concurrency 3
