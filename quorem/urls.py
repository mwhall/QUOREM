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
from django.conf.urls.static import static
from django.conf import settings
from landingpage.views import index
from db.views import *
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from db.models.object import Object

object_list = Object.get_object_types()

urlpatterns = []

urlpatterns += [
    # Main page routing
    path('', index, name='landing'),
    path('admin/', admin.site.urls),
    # Password Reset Routing
    re_path(r'^password_reset/$', auth_views.PasswordResetView.as_view(), name='password_reset'),
    re_path(r'^password_reset/done/$', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    re_path(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    re_path(r'^reset/done/$', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    # Wiki routing
    #path('notifications/', include('django_nyt.urls')),
    #path('wiki/', include('wiki.urls')),

    # Home Page after login

#    re_path(r'^home/$', main_page, name='main_page',
#                        kwargs={'view_title': 'Main page'}),
    path('home/', login_required(HomePageView.as_view(), login_url='/accounts/signin/'), name='homepage'),
    # Upload routing
#    path('upload/spreadsheet', spreadsheet_upload.as_view(), name='upload_spreadsheet'),
#    path('upload/spreadsheet-simple', simple_sample_metadata_upload.as_view(), name='upload_simple_spreadsheet'),
    re_path(r'^analysis/upload/$', login_required(AnalysisSelectView.as_view()), name='upload_analysis_select'),
    re_path(r'^analysis/(?P<analysis_id>\d+)/upload$', login_required(AnalysisFileFieldView.as_view()), name='upload_to_analysis'),
    re_path(r'^upload/spreadsheet/$', login_required(SpreadsheetFileFieldView.as_view()), name="spreadsheet_upload"),
    #Upload list.
#    re_path(r'upload/all/$', UploadList.as_view(), name='upload_all',
#        kwargs={'view_title':"All Uploads"}),
#    re_path(r'upload/(?P<uploadfile_id>\d+)/$', UploadFileDetail.as_view(),
#            name='uploadfile_detail',
#            kwargs={'view_title': "Upload Details"}),
#    path('upload/<int:uploadfile_id>/<new>/', UploadFileDetail.as_view(is_new=True),
#            name='uploadfile_detail_new',
#            kwargs={'view_title':"Upload Details"}),
    path('accounts/', include('accounts.urls')),
    # Sample Routing
    re_path(r'sample/(?P<sample_id>\d+)/$',
            login_required(SampleDetailView.as_view()),
                             name='sample_detail',
                             kwargs={'view_title': 'Sample Detail'}),

    re_path(r'sample/all/$', login_required(SampleFilterListView.as_view()), name="sample_all"),
#    re_path(r'sample/create/$', SampleCreate.as_view(),
#        name='sample_create',
#        kwargs={'view_title': 'Create New Sample'}),

    # Feature Routing
    re_path(r'feature/(?P<feature_id>\d+)/$',
            login_required(FeatureDetailView.as_view()),
                             name='feature_detail',
                             kwargs={'view_title': 'Feature Detail'}),
#    re_path(r'feature/create/$', FeatureCreate.as_view(),
#            name = 'feature_create',
#            kwargs = {'view_title': 'Create New Feature'}),
    re_path(r'feature/all/$', login_required(FeatureFilterListView.as_view()), name="feature_all"),

    # Investigation Routing
    re_path(r'investigation/(?P<investigation_id>\d+)/$',
            login_required(InvestigationDetailView.as_view()),
                             name='investigation_detail',
                             kwargs={'view_title': 'Investigation Detail'}),
    re_path(r'investigation/create/$', login_required(InvestigationCreateView.as_view()),
                                      name='investigation_create'),
    re_path(r'investigation/all/$', login_required(InvestigationFilterListView.as_view()), 
                                    name="investigation_all"),

    # Process Routing
    re_path(r'process/(?P<process_id>\d+)/$',
            login_required(ProcessDetailView.as_view()),
                             name='process_detail',
                             kwargs={'view_title': 'Process Detail'}),
    re_path(r'process/create/$', login_required(ProcessCreateView.as_view()),
        name = 'process_create'),
    re_path(r'process/all/$', login_required(ProcessFilterListView.as_view()), name="process_all"),

    # Step Routing
    re_path(r'step/(?P<step_id>\d+)/$',
            login_required(StepDetailView.as_view()),
                             name='step_detail',
                             kwargs={'view_title': 'Step Detail'}),

    re_path(r'step/create/$', login_required(StepCreateView.as_view()),
        name = 'step_create',
        kwargs={'view_title': "Create New Step", 'allow_anonymous': False}),
    re_path(r'step/all/$', login_required(StepFilterListView.as_view()), name="step_all"),

    # Result Routing
    re_path(r'result/(?P<result_id>\d+)/$',
            login_required(ResultDetailView.as_view()),
                             name='result_detail',
                             kwargs={'view_title': 'Result Detail'}),
    re_path(r'result/all/$', login_required(ResultFilterListView.as_view()), name="result_all"),

    # Analysis Routing
    re_path(r'analysis/(?P<analysis_id>\d+)/$',
            login_required(AnalysisDetailView.as_view()),
                             name='analysis_detail',
                             kwargs={'view_title': 'Analysis Detail'}),
    re_path(r'analysis/all/$', login_required(AnalysisFilterListView.as_view()), name="analysis_all"),
    re_path(r'analysis/create/$', login_required(AnalysisCreateView.as_view()),
            name = 'analysis_create'),

    #Value routing
    re_path(r'value/(?P<value_id>\d+)/$',
            login_required(ValueDetailView.as_view()),
            name='value_detail'),
    re_path(r'value/all/$', login_required(ValueFilterListView.as_view()), name="value_all"),

    #### Search Result Routing
    #path('search/', search, name='search-results'),

    #### analysis routing
    path('analyze/table/collapse/', TableCollapseView.as_view(), name='table_collapse'),
    path('plot/pcoa/', PCoAPlotView.as_view(), name='plot-pcoa'),
    path('plot/table/', TablePlotView.as_view(), name='plot-table'),
    path('plot/tree/', TreePlotView.as_view(), name='plot-tree'),

    ## Autocomplete Routing
    # See below for generic autcomplete magic
    re_path(r'^value-autocomplete/$',
            ValueAutocomplete.as_view(),
            name='value-autocomplete'),
    re_path(r'^object-autocomplete/$',
            ObjectAutocomplete.as_view(),
            name='object-autocomplete'),
    re_path(r'^object-autocomplete/result/tree/$',
            TreeResultAutocomplete.as_view(),
            name='result-tree-autocomplete'),
    re_path(r'^object-autocomplete/result/taxonomy/$',
            TaxonomyResultAutocomplete.as_view(),
            name='result-taxonomy-autocomplete'),
    re_path(r'^object-autocomplete/result/countmatrix/$',
            CountMatrixAutocomplete.as_view(),
            name='result-countmatrix-autocomplete'),
    re_path(r'^data-signature-autocomplete/$',
            DataSignatureAutocomplete.as_view(),
            name='data-signature-autocomplete'),
    re_path(r'^sample-metadata-autocomplete/$',
            SampleMetadataAutocomplete.as_view(),
            name='sample-metadata-autocomplete'),

    ## Mail routing
    path('mail/', MailBoxView.as_view(), name='mail'),
    re_path(r'mail/open/(?P<mail_id>\d+)/$', MailOpen.as_view(), name='open_mail'),

    #Download routing
    path('data-csv/', csv_download_view, name='csv_download'),
    path('data-xls/', xls_download_view, name='xls_download'),
    path('taxon-table/', tax_table_download_view, name="tax_table_download"),
    path('data-artifact/', artifact_download_view, name='artifact_download'),
    path('data-spreadsheet/', spreadsheet_download_view, name='spreadsheet_download'),

    #redirect no-auth users to here
    path('no-auth/', no_auth_view, name='noauth'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


#Generic autocomplete magic to get object-object relations as an autocomplete for quick and dirty dropdowns
for Obj in object_list:
    urlpatterns += [path('object-autocomplete/%s/' % (Obj.base_name,),
                             login_required(object_autocomplete_factory(Obj.base_name).as_view()),
                             name="object-%s-autocomplete"%(Obj.base_name,))]
for ObjA in Object.get_object_types():
    for ObjB in Object.get_object_types():
        urlpatterns.append(
                path('object-autocomplete/%s/%s/'%(ObjA.base_name, ObjB.base_name),
                     login_required(object_relation_view_factory(ObjA.base_name, ObjB.base_name).as_view()),
                     name="%sTo%s-autocomplete"%(ObjA.base_name, ObjB.base_name)))

#What's this for? Is it needed?
#js_info_dict = {
#            'domain': 'djangojs',
#            'packages': ('quorem',),
#                }
#
#try:
#    from django.views.i18n import JavaScriptCatalog
#    urlpatterns += [
#        re_path(r'^jsi18n/$', JavaScriptCatalog.as_view(**js_info_dict), name='javascript-catalog'),
#    ]
#except ImportError:
#    from django.views.i18n import javascript_catalog
#    urlpatterns += [
#        re_path(r'^jsi18n/$', javascript_catalog, js_info_dict, name='javascript-catalog',)
#    ]
