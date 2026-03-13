from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Invite

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("GostPillar Roles", {"fields": ("is_platform_admin",)}),
    )
    list_display = ("username", "email", "is_superuser", "is_platform_admin", "is_pentester", "is_staff", "is_active")

@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("email", "invited_by", "created_at", "expires_at", "used_at")
    search_fields = ("email",)
