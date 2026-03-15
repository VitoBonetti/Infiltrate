from django.db import models
import uuid as _uuid
from indicators.models import Tags, Flags

class Regions(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    region = models.CharField(max_length=120, unique=True)
    active =models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField(Tags, blank=True, related_name='region_tags')
    flags = models.ManyToManyField(Flags, blank=True, related_name='region_flags')

    class Meta:
        verbose_name_plural = "Regions"
        verbose_name = "Region"

    def __str__(self):
        return self.region