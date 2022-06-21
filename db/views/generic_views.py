# ----------------------------------------------------------------------------
# path: quorem/db/views/generic_views.py
# authors: Mike Hall
# modified: 2022-06-16
# description: This file contains all views that are for generic pages or
#              functions and utilities used in multiple views
# ----------------------------------------------------------------------------

import urllib

from django.shortcuts import render, redirect
from django.urls import reverse as django_reverse, reverse_lazy
from django.views.generic.base import TemplateView
from django.views.generic.list import ListView

from ..models import Feature, Sample, Result
from ..models.object import Object

def no_auth_view(request):
    return render(request, 'core/noauth.htm')

def reverse(*args, **kwargs):
    get = kwargs.pop('get', {})
    post = kwargs.pop('post', {})
    url = django_reverse(*args, **kwargs)
    if get:
        url += '?' + urllib.parse.urlencode(get)
    if post:
        postcopy = post.copy()
        postcopy.pop("csrfmiddlewaretoken")
        url += '?' + urllib.parse.urlencode(postcopy)
    return url

class HomePageView(TemplateView):
    template_name= "homepage.htm"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['feature_count'] = Feature.objects.count()
        context['sample_count'] = Sample.objects.count()
        context['result_count'] = Result.objects.count()
        return context

#Generic FilteredListView from caktusgroup.com/blog/2018/10/18/filtering-and-pagination-django/
class FilteredListView(ListView):
    filterset_class = None
    paginate_by = 20
    model = Object
    def get_queryset(self):
        queryset = super().get_queryset()
        self.filterset = self.filterset_class(self.request.GET, queryset=queryset)
        return self.filterset.qs.distinct()
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filterset'] = self.filterset
        context['base_name'] = self.model.base_name
        context['plural_name'] = self.model.plural_name
        return context
