from django.contrib import admin
from .models import Organization

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "market")
    list_filter = ("market",)
    search_fields = ("name",)