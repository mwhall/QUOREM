from django.templatetags.static import static
from django.urls import reverse

from jinja2 import Environment
from jinja2.runtime import Context
from .jinja.filters import highlight, add_type, format_pages

def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': static,
        'url': reverse,
    })
    env.filters.update({
        'highlight' : highlight,
        'add_type': add_type,
        'format_pages':format_pages,
    })
    return env
