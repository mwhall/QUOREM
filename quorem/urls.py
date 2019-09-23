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
from db.views_ajax import InvestigationGridView, SampleFkWidgetGrid, StepFkWidgetGrid
from db.views import (
    InvestigationCreate, InvestigationDetail, InvestigationList,
    InvestigationUpdate,
    ProcessCreate, ProcessDetail, ProcessList, ProcessUpdate,
    ResultList, ResultDetail,
    StepList, StepCreate, StepDetail, StepUpdate,
    FeatureList, FeatureDetail, FeatureCreate,
    SampleDetail, SampleList, SampleUpdate, SampleCreate,
    AnalysisDetail, AnalysisList, AnalysisCreate,
    UploadList, UploadInputFileDetail,
    #SearchResultList
    search,
    #analysis page
    analyze, new_upload, plot_view, ajax_aggregates_meta_view,
    PlotAggregateView, PlotTrendView, ajax_plot_trendx_view, ajax_plot_trendy_view,
)
from db.autocomplete_views import ValueAutocomplete, CategoryAutocomplete

urlpatterns = [
    # Main page routing
    path('admin/', admin.site.urls),
    # Wiki routing
    path('notifications/', include('django_nyt.urls')),
    path('wiki/', include('wiki.urls')),
    # Upload routing
    path('upload/new', new_upload.as_view(), name='upload'),
    #Upload list.
    re_path('upload/all', UploadList.as_view(), name='upload_all',
        kwargs={'view_title':"All Uploads"}),
    re_path(r'upload/(?P<uploadinputfile_id>\d+)/$', UploadInputFileDetail.as_view(),
            name='uploadinputfile_detail',
            kwargs={'view_title': "Upload Details"}),
    path('upload/<int:uploadinputfile_id>/<new>/', UploadInputFileDetail.as_view(is_new=True),
            name='uploadinputfile_detail_new',
            kwargs={'view_title':"Upload Details"}),
    path('accounts/', include('accounts.urls')),
    path('', index, name='landing'),
    # Investigation Routing
    re_path(r'investigation/all/$', InvestigationList.as_view(),
            name='investigation_all',
            kwargs={'view_title': 'All Investigations'}),
    re_path(r'investigation/create/$', InvestigationCreate.as_view(),
        name='investigation_create',
        kwargs={'view_title': "Create New Investigation", 'allow_anonymous': False}),
    re_path(r'investigation/(?P<investigation_id>\d+)/$', InvestigationDetail.as_view(),
        name='investigation_detail',
        kwargs={'view_title': 'All Investigations'}),
    re_path(r'investigation/edit/(?P<investigation_id>\d+)/$', InvestigationUpdate.as_view(),
        name='investigation_update',
        kwargs={'view_title': 'Update Investigation', 'allow_anonymous': False}),

    # Sample Routing
    re_path(r'sample/all/$', SampleList.as_view(),
            name = 'sample_all',
            kwargs = {'view_title': 'All Samples'}),
    re_path(r'sample/(?P<sample_id>\d+)/$', SampleDetail.as_view(),
        name='sample_detail',
        kwargs={'view_title': 'Sample Detail'}),
    re_path(r'sample/edit/(?P<sample_id>\d+)/$', SampleUpdate.as_view(),
        name='sample_update',
        kwargs={'view_title': 'Sample Update', 'allow_anonymous': False}),
    re_path(r'sample/create/$', SampleCreate.as_view(),
        name='sample_create',
        kwargs={'view_title': 'Create New Sample'}),

    # Feature Routing
    re_path(r'feature/all/$', FeatureList.as_view(),
            name = 'feature_all',
            kwargs = {'view_title': 'All Features'}),
    re_path(r'feature/(?P<feature_id>\d+)/$', FeatureDetail.as_view(),
            name = 'feature_detail',
            kwargs = {'view_title': 'Feature Details'}),
    re_path(r'feature/create/$', FeatureCreate.as_view(),
            name = 'feature_create',
            kwargs = {'view_title': 'Create New Feature'}),

    # Process Routing
    re_path(r'process/(?P<process_id>\d+)/$', ProcessDetail.as_view(),
        name='process_detail',
        kwargs={'view_title': "Process Detail"}),
    re_path(r'process/all/$', ProcessList.as_view(),
        name='process_all',
        kwargs={'view_title': "All Processs"}),
    re_path(r'process/create/$', ProcessCreate.as_view(),
        name = 'process_create',
        kwargs={'view_title': "Create New Process", 'allow_anonymous': False}),
    re_path(r'process/edit/(?P<process_id>\d+)/$', ProcessUpdate.as_view(),
        name = 'process_update',
        kwargs={'view_title': "Process Update", 'allow_anonymous': False}),

    # Result Routing
    re_path(r'result/all/$', ResultList.as_view(),
        name = 'result_all',
        kwargs={'view_title': "Result List", 'allow_anonymous': False}),
    re_path(r'result/(?P<result_id>\d+)/$', ResultDetail.as_view(),
            name='result_detail',
            kwargs={'view_title': "Result Detail"}),

    # Analysis Routing
    re_path(r'analysis/all/$', AnalysisList.as_view(),
            name = 'analysis_all',
            kwargs = {'view_title': "Analysis List", 'allow_anonymous': False}),
    re_path(r'analysis/(?P<analysis_id>\d+)/$', AnalysisDetail.as_view(),
            name = 'analysis_detail',
            kwargs={'view_title': "Analysis Detail"}),
    re_path(r'analysis/create/$', AnalysisCreate.as_view(),
            name = 'analysis_create',
            kwargs = {'view_title': "Create New Analysis"}),

    # Step Routing
    re_path(r'step/all/$', StepList.as_view(),
            name='step_all',
            kwargs={'view_title': "All Steps"}),
    re_path(r'step/create/$', StepCreate.as_view(),
        name = 'step_create',
        kwargs={'view_title': "Create New Step", 'allow_anonymous': False}),
    re_path(r'step/(?P<step_id>\d+)/$', StepDetail.as_view(),
        name = 'step_detail',
        kwargs={'view_title': "Step Detail"}),
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
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

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
