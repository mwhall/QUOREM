from django.shortcuts import redirect, render

#class ContextMiddleware(BaseContextMiddleware):
#
#    def add_action(self, obj, action_type):
#        self.__class__.add_instance('actions', (obj, action_type))
#
#    def save_actions(self, request):
#        pass
#
#    def process_view(self, request, view_func, view_args, view_kwargs):
#        result = super().process_view(request, view_func, view_args, view_kwargs)
#        self.save_actions(request)
#        return result

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
