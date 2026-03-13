from django.db import models
import uuid as _uuid


class Organization(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    market = models.ForeignKey("markets.Market", on_delete=models.CASCADE, related_name="orgs")
    name = models.CharField(max_length=200)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["market", "name"], name="uniq_org_per_market")
        ]

    def __str__(self):
        return f"{self.market} / {self.name}"
