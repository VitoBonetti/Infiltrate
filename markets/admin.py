from django.contrib import admin
from .models import Market

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ("market", "region")
    list_filter = ("region", "key_market")
    search_fields = ("market",)