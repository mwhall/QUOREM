from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

User = get_user_model()


class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="Confirm Password",
                                       widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}))

    class Meta:
        model = User
        fields = ('email',
                  'password',
                  )

    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)
        self.fields['email'].widget.attrs['placeholder'] = 'Email'
        self.fields['password'].widget.attrs['placeholder'] = 'Password'

    def passwords_match(self):
        if self.data['password'] == self.data['confirm_password']:
            return True
        else:
            return False


class SignInForm(forms.Form):
    email = forms.CharField(required=True, label="Email", max_length=40, widget=forms.TextInput(attrs={'placeholder': "Email"}))
    password = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
