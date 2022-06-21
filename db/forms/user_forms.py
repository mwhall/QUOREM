# ----------------------------------------------------------------------------
# path: quorem/db/forms/user_forms.py
# authors: Mike Hall
# modified: 2022-06-14
# description: This file contains all forms for user management
# ----------------------------------------------------------------------------

from ..models import UserProfile

from django.forms import ModelForm

class UserProfileForm(ModelForm):
    #ModelForm will auto-generate fields which dont already exist
    #Therefore, creating fields prevents auto-generation.
    class Meta:
        model = UserProfile
        fields = ['user']

