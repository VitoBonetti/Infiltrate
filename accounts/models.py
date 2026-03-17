from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import uuid as _uuid


class User(AbstractUser):
    id = models.UUIDField(default=_uuid.uuid4, primary_key=True, editable=False)
    # "Admin" (not Django admin site "staff")
    is_platform_admin = models.BooleanField(default=False)
    is_pentester = models.BooleanField(default=False)
    is_tester = models.BooleanField(default=False)

    def clean(self):
        # GOD vs Admin exclusivity
        if self.is_superuser and self.is_platform_admin:
            raise ValidationError("User cannot be both GOD (superuser) and Admin (platform admin).")

    def save(self, *args, **kwargs):
        # enforce exclusivity automatically
        if self.is_superuser:
            self.is_platform_admin = False
            self.is_pentester = False
            self.is_staff = True
            self.is_tester = True
        elif self.is_platform_admin:
            self.is_superuser = False
            self.is_pentester = False
            self.is_staff = True
            self.is_tester = False
        elif self.is_pentester:
            self.is_superuser = False
            self.is_platform_admin = False
            self.is_staff = False
            self.is_tester = True

        super().save(*args, **kwargs)

class Invite(models.Model):
    email = models.EmailField()
    token_hash = models.CharField(max_length=128, editable=False)
    invited_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and timezone.now() > self.expires_at

    def verify_token(self, raw_token: str) -> bool:
        return check_password(raw_token, self.token_hash)