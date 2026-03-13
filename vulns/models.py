from django.db import models
import uuid as _uuid


class Vulnerability(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    test = models.ForeignKey("tests.Test", on_delete=models.CASCADE, related_name="vulns")
    title = models.CharField(max_length=200)
    severity = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default="unpublished")
    description = models.TextField(blank=True)

    def __str__(self):
        return f"[{self.severity}] {self.title}"