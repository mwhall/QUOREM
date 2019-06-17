from django.urls import path, re_path
from . import views


app_name = 'accounts'

urlpatterns = [
    path('signup/', views.account_signup, name='signup'),
    path('signin/', views.account_signin, name='signin'),
    path('edit/', views.account_edit, name='edit'),
    path('logout/', views.account_logout, name='logout'),
    path('login/', views.account_signin, name='login'),


]
