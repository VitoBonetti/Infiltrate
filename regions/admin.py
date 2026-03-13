from django.contrib import admin
from .models import Regions

@admin.register(Regions)
class RegionAdmin(admin.ModelAdmin):
    search_fields = ("region",)