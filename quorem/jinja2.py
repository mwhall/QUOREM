from django.templatetags.static import static
from django.urls import reverse

from jinja2 import Environment
from .jinja.filters import highlight

def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'static': static,
        'url': reverse,
    })
    env.filters.update({
        'highlight' : highlight
    })
    return env
