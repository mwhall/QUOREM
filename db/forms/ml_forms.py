# ----------------------------------------------------------------------------
# path: quorem/db/forms/ml_forms.py
# authors: Mike Hall
# modified: 2022-06-15
# description: This file contains all machine learning forms
# ----------------------------------------------------------------------------

from django import forms
from django.utils.html import format_html, mark_safe
from ..models import (
    Investigation,
    Process, Step, Analysis,
    Result,
    Sample, Feature
)

from dal import autocomplete

#Machine learning forms will be input here when merged
