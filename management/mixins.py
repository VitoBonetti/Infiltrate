from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from rbac.management_policy import can_access_management, admin_can_write, admin_can_delete

class ManagementAccessMixin(LoginRequiredMixin):
    """
    Blocks everything unless GOD/Admin.
    """
    def dispatch(self, request, *args, **kwargs):
        if not can_access_management(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class ManagementWriteMixin(ManagementAccessMixin):
    """
    Allows to create/update only if policy allows.
    """
    def dispatch(self, request, *args, **kwargs):
        if not admin_can_write(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class ManagementDeleteMixin(ManagementAccessMixin):
    """
    Allows to delete only if policy allows (GOD only in our example).
    """
    def dispatch(self, request, *args, **kwargs):
        if not admin_can_delete(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)