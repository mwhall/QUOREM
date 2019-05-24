import re
from jinja2 import Markup

def highlight(text, selection):
    if not text:
        return
    pattern = re.compile(selection, re.IGNORECASE)
    l = re.findall(pattern, text)
    l = list(set(l))
    #<mark> tags highlight text in BS4.
    for i in l:
        text = text.replace(i, "<mark>{0}</mark>".format(i))
    return Markup(text)
