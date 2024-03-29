from django.shortcuts import redirect, render

class UserAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response


    def process_view(self, request, view_func, view_args, view_kwargs):
        #if user has no_auth then redirect them
        if request.user.is_authenticated:
            if request.user.is_superuser == False and request.user.has_access == False and request.path not in  ['/no-auth/', '/accounts/logout/']:
                return render(request, 'landingpage/landingpage.html')
        #otherwise proceed as normal

        return None
