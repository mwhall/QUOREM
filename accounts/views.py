from django.shortcuts import render, redirect
from .forms import SignInForm, SignUpForm
from django.contrib.auth import authenticate, login, logout
from django.apps import apps
from db.models import User

UserProfile = apps.get_model("db", "UserProfile")

def account_signup(request):
    form = SignUpForm(request.POST or None)
    action = 'SignUp'


    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        if form.passwords_match():
            user.set_password(password)
            user.save()
        #    up = UserProfile.create(user=user)
        #    up.save()
            authenticate(email=email, password=password)
            login(request, user)
            return redirect('homepage')

    elif request.method == 'POST':
        email = request.POST['email']
        if User.objects.filter(email=email):
            return render(request, 'accounts/signup.html', context={'form': form, 'action': action, 'taken':True} )

    return render(request, 'accounts/signup.html', context={'form': form, 'action': action})


def account_signin(request):
    form = SignInForm(request.POST or None)
    action = 'SignIn'
    login_failed = False
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = authenticate(email=email, password=password)
        if user:
            login(request, user)
            return redirect('homepage')
        else:
            login_failed = True
    return render(request, 'accounts/signin.html', context={'form': form,
                                                            'action': action,
                                                            'failed': login_failed})


def account_logout(request):
    logout(request)
    return redirect('landing')


def account_edit(request):
    pass


def forgot_password(request):
    pass

"""
def unauthorized(request):
    print("AUTH CHECK FAILED")
    return redirect('landing')
"""
