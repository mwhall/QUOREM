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
from landingpage.views import index
from db.views_ajax import InvestigationGridView, ReplicateFkWidgetGrid, SampleFkWidgetGrid, ProtocolStepFkWidgetGrid
from db.views import (
    InvestigationCreate, InvestigationDetail, InvestigationList,
    InvestigationUpdate, InvestigationMetadataDetail,
    ProtocolCreate, ProtocolDetail, ProtocolList, ProtocolUpdate,
    ProtocolStepCreate, ProtocolStepDetail,
    ProtocolStepList, ProtocolStepUpdate,
    PipelineCreate, PipelineDetail, PipelineList, PipelineUpdate,
    PipelineResultList,
    PipelineStepCreate, PipelineStepDetail,
    PipelineStepList, PipelineStepUpdate,
    ReplicateDetail, ReplicateUpdate, ReplicateList,
    SampleDetail, SampleList, SampleUpdate, UploadCreate, UploadList, UploadInputFileDetail,
    #SearchResultList
    search
)

urlpatterns = [
    # Main page routing
    path('admin/', admin.site.urls),
    re_path('upload/new', UploadCreate.as_view(), name='upload',
        kwargs={'view_title': "Upload Data"} ),
    #Upload list.
    re_path('upload/all', UploadList.as_view(), name='upload_all',
        kwargs={'view_title':"All Uploads"}),
    re_path(r'upload/(?P<uploadinputfile_id>\d+)/$', UploadInputFileDetail.as_view(),
            name='uploadinputfile_detail',
            kwargs={'view_title': "Upload Details", "allow_anonymous": True}),
    path('account/', include('accounts.urls')),
    path('', index, name='landing'),
    # Investigation Routing
    re_path(r'investigation/all(?P<action>/?\w*)/$', InvestigationList.as_view(),
            name='investigation_all',
            kwargs={'view_title': 'All Investigations'}),
    re_path(r'investigation/all/$', InvestigationList.as_view(),
            name='investigation_all',
            kwargs={'view_title': 'All Investigations'}),
    re_path(r'investigation/create/$', InvestigationCreate.as_view(),
        name='investigation_create',
        kwargs={'view_title': "Create New Investigation", 'allow_anonymous': False}),
    re_path(r'investigation/(?P<investigation_id>\d+)/$', InvestigationDetail.as_view(),
        name='investigation_detail',
        kwargs={'view_title': 'All Investigations', 'allow_anonymous': True}),
    re_path(r'investigation/edit/(?P<investigation_id>\d+)/$', InvestigationUpdate.as_view(),
        name='investigation_update',
        kwargs={'view_title': 'Update Investigation', 'allow_anonymous': False}),

    # Sample Routing
    re_path(r'sample/all/$', SampleList.as_view(),
            name = 'sample_all',
            kwargs = {'view_title': 'All Samples', 'allow_anonymous': True}),
    re_path(r'sample/(?P<sample_id>\d+)/$', SampleDetail.as_view(),
        name='sample_detail',
        kwargs={'view_title': 'Sample Detail', 'allow_anonymous': True}),
    re_path(r'sample/edit/(?P<sample_id>\d+)/$', SampleUpdate.as_view(),
        name='sample_update',
        kwargs={'view_title': 'Sample Update', 'allow_anonymous': False}),

# Replicate Routing
    re_path(r'replicate/all/$', ReplicateList.as_view(),
            name = 'replicate_all',
            kwargs = {'view_title': 'All Replicates', 'allow_anonymous': True}),
    re_path(r'replicate/(?P<replicate_id>\d+)/$', ReplicateDetail.as_view(),
        name='replicate_detail',
        kwargs={'view_title': 'Replicate Detail', 'allow_anonymous': True}),
    re_path(r'replicate/edit/(?P<replicate_id>\d+)/$', ReplicateUpdate.as_view(),
        name='replicate_update',
        kwargs={'view_title': 'Replicate Update', 'allow_anonymous': False}),



    # Investigation Metadata Routing
    re_path(r'investigation/metadata/(?P<investigation_id>\d+)/$', InvestigationMetadataDetail.as_view(),
        name='investigation_metadata_detail',
        kwargs={'view_title': 'Investigation Metadata', 'allow_anonymous': True}),

    # Replicate Routing
    # Replicates are added via the Sample edit page. Should there be replicate
    # specific pages?

    # Protocol Routing
    re_path(r'protocol/(?P<protocol_id>\d+)/$', ProtocolDetail.as_view(),
        name='protocol_detail',
        kwargs={'view_title': "Protocol Detail", 'allow_anonymous': True}),
    re_path(r'protocol/all/$', ProtocolList.as_view(),
        name='protocol_all',
        kwargs={'view_title': "All Protocols", 'allow_anonymous': True}),
    re_path(r'protocol/create/$', ProtocolCreate.as_view(),
        name = 'protocol_create',
        kwargs={'view_title': "Create New Protocol", 'allow_anonymous': False}),
    re_path(r'protocol/edit/(?P<protocol_id>\d+)/$', ProtocolUpdate.as_view(),
        name = 'protocol_update',
        kwargs={'view_title': "Protocol Update", 'allow_anonymous': False}),

    # Protocol Step Routing
    re_path(r'protocol/step/all/$', ProtocolStepList.as_view(),
            name='protocol_step_all',
            kwargs={'view_title': "All Protocol Steps", 'allow_anonymous': True}),
    re_path(r'protocol/step/create/$', ProtocolStepCreate.as_view(),
        name = 'protocol_step_create',
        kwargs={'view_title': "Create New Protocol Step", 'allow_anonymous': False}),
    re_path(r'protocol/step/(?P<protocol_step_id>\d+)/$', ProtocolStepDetail.as_view(),
        name = 'protocol_step_detail',
        kwargs={'view_title': "Protocol Step Detail", 'allow_anonymous': True}),
    re_path(r'protocol/step/edit/(?P<protocol_step_id>\d+)/$', ProtocolStepUpdate.as_view(),
        name = 'protocol_step_update',
        kwargs = {'view_title': "Protocol Step Update", 'allow_anonymous': False}),

    # Pipeline Routing
    re_path(r'pipeline/(?P<pipeline_id>\d+)/$', PipelineDetail.as_view(),
        name='pipeline_detail',
        kwargs={'view_title': "Pipeline Detail", 'allow_anonymous': True}),
    re_path(r'pipeline/all/$', PipelineList.as_view(),
        name='pipeline_all',
        kwargs={'view_title': "All Pipelines", 'allow_anonymous': True}),
    re_path(r'pipeline/create/$', PipelineCreate.as_view(),
        name = 'pipeline_create',
        kwargs={'view_title': "Create New Pipeline", 'allow_anonymous': False}),
    re_path(r'pipeline/edit/(?P<pipeline_id>\d+)/$', PipelineUpdate.as_view(),
        name = 'pipeline_update',
        kwargs={'view_title': "Pipeline Update", 'allow_anonymous': False}),
    re_path(r'pipeline/result/all/$', PipelineResultList.as_view(),
        name = 'pipeline_result_all',
        kwargs={'view_title': "Pipeline Update", 'alllow_anonymous': False}),

    # Protocol Step Routing
    re_path(r'pipeline/step/all/$', PipelineStepList.as_view(),
            name='pipeline_step_all',
            kwargs={'view_title': "All Pipeline Steps", 'allow_anonymous': True}),
    re_path(r'pipeline/step/create/$', PipelineStepCreate.as_view(),
        name = 'pipeline_step_create',
        kwargs={'view_title': "Create New Pipeline Step", 'allow_anonymous': False}),
    re_path(r'pipeline/step/(?P<pipeline_step_id>\d+)/$', PipelineStepDetail.as_view(),
        name = 'pipeline_step_detail',
        kwargs={'view_title': "Pipeline Step Detail", 'allow_anonymous': True}),
    re_path(r'pipeline/step/edit/(?P<pipeline_step_id>\d+)/$', PipelineStepUpdate.as_view(),
        name = 'pipeline_step_update',
        kwargs = {'view_title': "Pipeline Step Update", 'allow_anonymous': False}),


    # Inline Forim Routing, AJAX FkWidgetGrids, currently unused
    re_path(r'protocol-step-grid(?P<action>/?\w*)/$', ProtocolStepFkWidgetGrid.as_view(),
        name='protocol_step_grid', kwargs={'ajax':True}),
    re_path(r'sample-grid(?P<action>/?\w*)/$', SampleFkWidgetGrid.as_view(),
        name='sample_grid', kwargs={'ajax':True}),
    re_path(r'replicate-grid(?P<action>/?\w*)/$', ReplicateFkWidgetGrid.as_view(),
        name='replicate_grid', kwargs={'ajax':True}),

    #Search Result Routing
    path('search/', search, name='search-results'),

]

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
