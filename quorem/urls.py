"""quorem URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf.urls import url
from django.conf.urls.static import static
from django.conf import settings
from landingpage.views import index
from db.views import *
from db.autocomplete_views import ValueAutocomplete, CategoryAutocomplete, object_relation_view_factory, ObjectAutocomplete

from db.models.object import Object

object_list = Object.get_object_types()

urlpatterns = []

for Obj in object_list:
    urlpatterns += [re_path(r'%s/(?P<%s_id>\d+)/$' % (Obj.base_name, Obj.base_name),
                     Obj.get_detail_view(as_view=True),
                     name= Obj.base_name + '_detail',
                     kwargs={'view_title': 'List of %s' % (Obj.plural_name,)}),
                     re_path(r'%s/all/$' % (Obj.base_name,), Obj.get_list_view(as_view=True),
                         name=Obj.base_name+"_all",
                         kwargs={"view_title": 'All %s' % (Obj.plural_name.capitalize())})]
urlpatterns += [
    # Main page routing
    path('admin/', admin.site.urls),
    # Wiki routing
    path('notifications/', include('django_nyt.urls')),
    path('wiki/', include('wiki.urls')),
    # Home Page after login
    path('home/', HomePage.as_view(), name='homepage'),
    # Upload routing
    path('upload/spreadsheet', spreadsheet_upload.as_view(), name='upload_spreadsheet'),
    path('upload/artifact', artifact_upload.as_view(), name='upload_artifact'),
    #Upload list.
    re_path(r'upload/all/$', UploadList.as_view(), name='upload_all',
        kwargs={'view_title':"All Uploads"}),
    re_path(r'upload/(?P<uploadfile_id>\d+)/$', UploadFileDetail.as_view(),
            name='uploadfile_detail',
            kwargs={'view_title': "Upload Details"}),
    path('upload/<int:uploadfile_id>/<new>/', UploadFileDetail.as_view(is_new=True),
            name='uploadfile_detail_new',
            kwargs={'view_title':"Upload Details"}),
    path('accounts/', include('accounts.urls')),
    path('', index, name='landing'),
    # Investigation Routing
    re_path(r'investigation/create/$', InvestigationCreate.as_view(),
        name='investigation_create',
        kwargs={'view_title': "Create New Investigation", 'allow_anonymous': False}),
    re_path(r'investigation/edit/(?P<investigation_id>\d+)/$', InvestigationUpdate.as_view(),
        name='investigation_update',
        kwargs={'view_title': 'Update Investigation', 'allow_anonymous': False}),

    # Sample Routing
    re_path(r'sample/edit/(?P<sample_id>\d+)/$', SampleUpdate.as_view(),
        name='sample_update',
        kwargs={'view_title': 'Sample Update', 'allow_anonymous': False}),
    re_path(r'sample/create/$', SampleCreate.as_view(),
        name='sample_create',
        kwargs={'view_title': 'Create New Sample'}),

    # Feature Routing
    re_path(r'feature/create/$', FeatureCreate.as_view(),
            name = 'feature_create',
            kwargs = {'view_title': 'Create New Feature'}),

    # Process Routing
    re_path(r'process/create/$', ProcessCreate.as_view(),
        name = 'process_create',
        kwargs={'view_title': "Create New Process", 'allow_anonymous': False}),
    re_path(r'process/edit/(?P<process_id>\d+)/$', ProcessUpdate.as_view(),
        name = 'process_update',
        kwargs={'view_title': "Process Update", 'allow_anonymous': False}),


    # Analysis Routing
    re_path(r'analysis/create/$', AnalysisCreate.as_view(),
            name = 'analysis_create',
            kwargs = {'view_title': "Create New Analysis"}),

    re_path(r'step/create/$', StepCreate.as_view(),
        name = 'step_create',
        kwargs={'view_title': "Create New Step", 'allow_anonymous': False}),
    re_path(r'step/edit/(?P<step_id>\d+)/$', StepUpdate.as_view(),
        name = 'step_update',
        kwargs = {'view_title': "Step Update", 'allow_anonymous': False}),


    # Inline Forim Routing, AJAX FkWidgetGrids, currently unused
#    re_path(r'process-step-grid(?P<action>/?\w*)/$', StepFkWidgetGrid.as_view(),
#        name='process_step_grid', kwargs={'ajax':True}),
#    re_path(r'sample-grid(?P<action>/?\w*)/$', SampleFkWidgetGrid.as_view(),
#        name='sample_grid', kwargs={'ajax':True}),
#    re_path(r'replicate-grid(?P<action>/?\w*)/$', ReplicateFkWidgetGrid.as_view(),
#        name='replicate_grid', kwargs={'ajax':True}),

    #### Search Result Routing
    path('search/', search, name='search-results'),

    #### analysis routing
    path('analyze/', analyze, name='analysis'),
    ### plot Routing
    path('analyze/plot/', plot_view, name='plot'),
    ## Aggregate routing
    path('analyze/plot/aggregate/', PlotAggregateView.as_view(), name='plot_aggregate'),
    path('ajax/model-options/', ajax_aggregates_meta_view, name="ajax_load_model_options"),
    ## Trend Routing
    path('ajax/trendx-options/', ajax_plot_trendx_view, name="ajax_trend_x_options"),
    path("ajax/trendy-options/", ajax_plot_trendy_view, name="ajax_trend_y_options"),
    path('analyze/plot/trend/', PlotTrendView.as_view(), name='plot_trend'),

    ## Autocomplete Routing
    re_path(r'^value-autocomplete/$',
            ValueAutocomplete.as_view(),
            name='value-autocomplete'),
    re_path(r'^category-autocomplete/$',
            CategoryAutocomplete.as_view(),
            name='category-autocomplete'),
    re_path(r'^object-autocomplete/$',
            ObjectAutocomplete.as_view(),
            name='object-autocomplete'),
    ##onto test
    path('ontology/viewer/', onto_view, name='onto_view'),
    path('ajax/load-onto/', onto_json, name='onto_json'),
    path('mail/', MailBoxView.as_view(), name='mail'),
    re_path(r'mail/open/(?P<mail_id>\d+)/$', MailOpen.as_view(), name='open_mail'),

    #value table views
    path('values/', ValueTableView.as_view(), name='value_table'),
    path('ajax/value-names/', ajax_value_table_view, name='ajax_value_names'),
    path('ajax/field-names-y/', ajax_value_table_related_models_view, name='ajax_field_names_y' ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

for ObjA in Object.get_object_types():
    for ObjB in Object.get_object_types():
        urlpatterns.append(
                path('object-autocomplete/%s/%s/'%(ObjA.base_name, ObjB.base_name),
                     object_relation_view_factory(ObjA.base_name, ObjB.base_name).as_view(), 
                     name="%sTo%s-autocomplete"%(ObjA.base_name, ObjB.base_name)))

js_info_dict = {
            'domain': 'djangojs',
            'packages': ('quorem',),
                }

try:
    from django.views.i18n import JavaScriptCatalog
    urlpatterns += [
        url(r'^jsi18n/$', JavaScriptCatalog.as_view(**js_info_dict), name='javascript-catalog'),
    ]
except ImportError:
    from django.views.i18n import javascript_catalog
    urlpatterns += [
        url(r'^jsi18n/$', javascript_catalog, js_info_dict, name='javascript-catalog',)
    ]
