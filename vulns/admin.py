from django.contrib import admin
from .models import Vulnerability

@admin.register(Vulnerability)
class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "status", "test")
    list_filter = ("severity", "status")
    search_fields = ("title",)