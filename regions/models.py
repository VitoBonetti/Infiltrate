from django.db import models
import uuid as _uuid

class Regions(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    region = models.CharField(max_length=120, unique=True)
    active =models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Regions"
        verbose_name = "Region"

    def __str__(self):
        return self.region