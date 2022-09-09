from .sample_views import ( SampleDetailView, 
                            SampleFilterListView )
from .feature_views import ( FeatureDetailView, 
                             FeatureFilterListView )
from .analysis_views import ( AnalysisDetailView, 
                              AnalysisSelectView, 
                              AnalysisFilterListView,
                              AnalysisCreateView )
from .step_views import ( StepDetailView, 
                          StepFilterListView,
                          StepCreateView )
from .process_views import ( ProcessDetailView, 
                             ProcessFilterListView, 
                             ProcessCreateView )
from .result_views import ( ResultDetailView, 
                            ResultFilterListView )
from .investigation_views import ( InvestigationDetailView, 
                                   InvestigationFilterListView, 
                                   InvestigationCreateView )
from .value_views import *
from .user_views import *
from .ml_views import *
from .plot_views import *
from .upload_views import *
from .mail_views import *
from .download_views import *
from .generic_views import HomePageView, no_auth_view
from .autocomplete_views import *
