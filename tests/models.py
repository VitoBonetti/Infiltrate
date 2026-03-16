from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
import uuid as _uuid
from indicators.models import Tags, Flags


SERVICE_TYPE_CHOICES = [
    ('Adversary Simulation', 'Adversary Simulation'),
    ('White Box', 'White Box'),
    ('Black Box', 'Black Box'),
]

TEST_STATUS_CHOICES = [
    ('Requested', 'Requested'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
    ('In Progress', 'In Progress'),
    ('Completed', 'Completed'),
    ('On Hold', 'On Hold'),
    ('Re Progress', 'Re Progress'),
    ('Cancelled', 'Cancelled'),
]

class Test(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    name = models.CharField(blank=True)
    assets = models.ManyToManyField("assets.Asset", related_name="tests", blank=True)
    service = models.CharField(choices=SERVICE_TYPE_CHOICES, max_length=50, default='Black Box')
    status = models.CharField(choices=TEST_STATUS_CHOICES, max_length=50, default='Requested')
    ritm = models.CharField(max_length=100, blank=True,
                            help_text="Attach a specific RITM or leave as standard.")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='requested_tests'
    )
    proposal_date = models.DateField(null=True, blank=True)
    quarter = models.CharField(max_length=10, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    tags = models.ManyToManyField(Tags, blank=True, related_name='test_tags')
    flags = models.ManyToManyField(Flags, blank=True, related_name='test_flags')
    description = models.CharField(null=True, blank=True)

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

    def save(self, *args, **kwargs):
        # calculate/update the quarter based on the proposal_date
        if self.proposal_date:
            q = (self.proposal_date.month - 1) // 3 + 1
            self.quarter = f"Q{q} {self.proposal_date.year}"
        else:
            self.quarter = None

        # assign start_date when status switches to 'In Progress'
        if self.status == 'In Progress' and not self.start_date:
            self.start_date = timezone.now().date()

        # assign end_date when status switches to 'Completed'
        if self.status == 'Completed' and not self.end_date:
            self.end_date = timezone.now().date()

        super().save(*args, **kwargs)


@receiver(m2m_changed, sender=Test.assets.through)
def update_test_name_on_assets_change(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        current_year = str(timezone.now().year)
        asset_names = " - ".join([asset.name for asset in instance.assets.all()])

        if not asset_names:
            asset_names = "No_Assets"

        new_name = f"{current_year} - {asset_names} - {instance.service}"

        if instance.name != new_name:
            instance.name = new_name
            instance.save(update_fields=['name'])