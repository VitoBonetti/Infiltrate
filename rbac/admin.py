from django.contrib import admin
from .models import RoleAssignment


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "scope_display", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")

    @admin.display(description="Scope")
    def scope_display(self, obj: RoleAssignment):
        # show the actual linked object nicely
        return obj.get_scope()