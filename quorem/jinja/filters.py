import re
from jinja2 import Markup
from jinja2 import contextfilter
from django.utils.http import urlencode
from django.shortcuts import render
from db.models import UserMail, UserProfile
from django.contrib.auth import get_user_model

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

def show_inbox(label, user):
    User = get_user_model()
    num_unreads = UserMail.objects.filter(user=UserProfile.objects.get(user=User.objects.get(email=user)),
                                            read=False).count()
    out = ""
    if num_unreads > 0:
        out = "<span class='badge badge-pill badge-warning'>"
    else:
        out = "<span class='badge badge-pill badge-secondary'>"
    out += str(num_unreads)
    out += "</span>"
    return Markup(out)


@contextfilter
def add_type(context, type_name):
    q_dict = context.copy()
    q_dict['selected']['type'] = type_name
    return render(request, 'search/search_results.htm', q_dict)

def format_pages(paginator, current_page, neighbors=5):
    if paginator.num_pages > 2*neighbors:
        start_index = max(1, current_page-neighbors)
        end_index = min(paginator.num_pages, current_page + neighbors)
        if end_index < start_index + 2*neighbors:
            end_index = start_index + 2*neighbors
        elif start_index > end_index - 2*neighbors:
            start_index = end_index - 2*neighbors
        if start_index < 1:
            end_index -= start_index
            start_index = 1
        elif end_index > paginator.num_pages:
            start_index -= (end_index-paginator.num_pages)
            end_index = paginator.num_pages
        page_list = [f for f in range(start_index, end_index+1)]
        return page_list[:(2*neighbors + 1)]
    return paginator.page_range

#Generate pagination links that don't discard the search filters.
@contextfilter
def page_url(context, page_num):
    ctx = context['request'].GET.copy()
    ctx['page'] = str(page_num)
    return '?' + ctx.urlencode()


@contextfilter
def add_facet(context, changes):
    ctx = context['request'].GET.copy()
    for key in changes.keys():
        ctx[key] = changes[key]
    return '?' + ctx.urlencode()

@contextfilter
def remove_facet(context, keys):
    ctx = context['request'].GET.copy()
    for key in keys:
        if key in ctx:
            ctx.pop(key)
    return '?' + ctx.urlencode()
