from django.db import models
from django.utils import timezone


class SingletonModel(models.Model):
    # Ensure only one record exists for the configuration.
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PlatformConfiguration(SingletonModel):

    CURRENT_YEAR = timezone.now().year

    # SLA Settings
    critical_sla_days = models.IntegerField(default=14, help_text="Days to fix Critical vulns")
    high_sla_days = models.IntegerField(default=30, help_text="Days to fix High vulns")
    medium_sla_days = models.IntegerField(default=45, help_text="Days to fix Medium vulns")
    low_sla_days = models.IntegerField(default=60, help_text="Days to fix Low vulns")
    info_sla_days = models.IntegerField(default=270, help_text="Days to fix Info vulns")

    # Vuln KPI year Target
    vuln_kpi_year = models.IntegerField(default=CURRENT_YEAR, null=True, blank=True)

    # KPI Criteria Setting
    kpi_min_cia = models.IntegerField(
        default=5,
        help_text="Minimum CIA score (e.g., 5). Logic will also include 0 or Null."
    )
    kpi_target_stages = models.CharField(
        max_length=255,
        default="In production",
        help_text="Comma-separated stages. E.g., 'In Production,Outphasing'"
    )
    kpi_target_types = models.CharField(
        max_length=255,
        default="Application,Web Application/Website",
        help_text="Comma-separated types to include."
    )
    kpi_target_as_a_service = models.CharField(
        max_length=255,
        default="None of the above",
        help_text="Comma-separated As-A-Service values to include."
    )

    class Meta:
        verbose_name = "Platform Configuration"
        verbose_name_plural = "Platform Configuration"

    def __str__(self):
        return "Global Settings"

    # Helper methods to convert comma-separated strings to clean lists
    def get_valid_stages(self):
        if not self.kpi_target_stages: return []
        return [s.strip().lower() for s in self.kpi_target_stages.split(',')]

    def get_valid_types(self):
        if not self.kpi_target_types: return []
        return [t.strip().lower() for t in self.kpi_target_types.split(',')]

    def get_valid_aas(self):
        if not self.kpi_target_as_a_service: return []
        return [a.strip().lower() for a in self.kpi_target_as_a_service.split(',')]