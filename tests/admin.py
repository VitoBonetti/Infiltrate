from django.contrib import admin
from .models import Test

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date")
    search_fields = ("name",)