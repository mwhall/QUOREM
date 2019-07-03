import re
from jinja2 import Markup
from django.utils.http import urlencode
from django.shortcuts import render

def highlight(text, selection):
    if not text:
        return
    if not selection:
        return Markup(text)
    pattern = re.compile(selection, re.IGNORECASE)
    l = re.findall(pattern, text)
    l = list(set(l))
    #<mark> tags highlight text in BS4.
    for i in l:
        text = text.replace(i, "<mark>{0}</mark>".format(i))
    return Markup(text)

def add_type(context, type_name):
    q_dict = context.copy()
    q_dict['selected']['type'] = type_name
    return render(request, 'search_results.htm', q_dict)
