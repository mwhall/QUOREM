from django_jinja_knockout.middleware import ContextMiddleware as BaseContextMiddleware

class ContextMiddleware(BaseContextMiddleware):

    def add_action(self, obj, action_type):
        self.__class__.add_instance('actions', (obj, action_type))

    def save_actions(self, request):
        pass

    def process_view(self, request, view_func, view_args, view_kwargs):
        result = super().process_view(request, view_func, view_args, view_kwargs)
        self.save_actions(request)
        return result
