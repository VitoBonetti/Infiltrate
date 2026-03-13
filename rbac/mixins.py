from django.core.exceptions import PermissionDenied
from rbac.policy import can_view, can_edit

class ViewPermissionRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not can_view(request.user, obj):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class EditPermissionRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not can_edit(request.user, obj):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)