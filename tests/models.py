from django.core.exceptions import ValidationError
from django.db import models
import uuid as _uuid

class Test(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    name = models.CharField(max_length=200)
    assets = models.ManyToManyField("assets.Asset", related_name="tests", blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name

    def clean(self):
        """
        Enforce: a Test can include multiple assets,
        but ALL assets must belong to the SAME market.
        """
        super().clean()
        if not self.uuid:
            return  # M2M not available until saved

        qs = self.assets.select_related("organization__market").all()
        market_ids = {a.organization.market_id for a in qs}
        if len(market_ids) > 1:
            raise ValidationError("A Test cannot span multiple markets. All assets must be in the same market.")
