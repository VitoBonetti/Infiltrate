from django.db import models
import uuid as _uuid


class Asset(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Pending', 'Pending'),
        ('Archived', 'Archived'),
    ]

    STAGE_CHOICES = [
        ('In Production', 'In Production'),
        ('Decommissioned', 'Decommissioned'),
        ('In design', 'In design'),
        ('In Development', 'In Development'),
        ('Outphasing', 'Outphasing'),
        ('Planned to be onboarded', 'Planned to be onboarded'),
    ]

    TYPE_CHOICES = [
        ('3rd part add-on to Hyperion', '3rd part add-on to Hyperion'),
        ('API', 'API'),
        ('Api integration con Bormaket', 'Api integration con Bormaket'),
        ('Application', 'Application'),
        ('Application/database', 'Application/database'),
        ('Backend AI agent', 'Backend AI agent'),
        ('BI & Analytics platorm', 'BI & Analytics platorm'),
        ('Child asset', 'Child asset'),
        ('Cloud Storage', 'Cloud Storage'),
        ('Combi Application', 'Combi Application'),
        ('Component', 'Component'),
        ('Componente', 'Componente'),
        ('Data Dashboard', 'Data Dashboard'),
        ('Data Source', 'Data Source'),
        ('Data Visualization', 'Data Visualization'),
        ('Database', 'Database'),
        ('Database/Data Source', 'Database/Data Source'),
        ('Datenbank', 'Datenbank'),
        ('Engine', 'Engine'),
        ('Extension / Add-on', 'Extension / Add-on'),
        ('Hardware', 'Hardware'),
        ('Infrastructure', 'Infrastructure'),
        ('Infrastructure/Platform', 'Infrastructure/Platform'),
        ('IT solution', 'IT solution'),
        ('Physical devices and peripherals', 'Physical devices and peripherals'),
        ('Physical Storage', 'Physical Storage'),
        ('Platform', 'Platform'),
        ('platform + application + internal web application', 'platform + application + internal web application'),
        ('Reports', 'Reports'),
        ('SAAS application neither hosted nor maintained by Randstad',
         'SAAS application neither hosted nor maintained by Randstad'),
        ('Search Engine', 'Search Engine'),
        ('SFTP Storage', 'SFTP Storage'),
        ('Sub application', 'Sub application'),
        ('Vendor', 'Vendor'),
        ('Web Application/Website', 'Web Application/Website'),
        ('Web Portal', 'Web Portal'),
        ('Website', 'Website'),
        ('website(op.randstad.com.tr) and database', 'website(op.randstad.com.tr) and database'),
        ('other', 'Other'),
    ]

    AS_SERVICE_CHOICES = [
        ('SaaS', 'SaaS'),
        ('IaaS', 'IaaS'),
        ('PaaS', 'PaaS'),
        ('None of above', 'None of above'),
    ]

    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    ID = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=200)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="assets_org")
    hosting_location = models.CharField(max_length=200, null=True, blank=True)
    asset_type = models.CharField(max_length=80, choices=TYPE_CHOICES, null=True, blank=True)
    asset_status = models.CharField(max_length=80, choices=STATUS_CHOICES, null=True, blank=True)
    asset_stage = models.CharField(max_length=80, choices=STAGE_CHOICES, null=True, blank=True)
    cia_score = models.IntegerField(null=True, blank=True)
    confidentiality_score = models.IntegerField(null=True, blank=True)
    integrity_score = models.IntegerField(null=True, blank=True)
    availability_score = models.IntegerField(null=True, blank=True)
    internet_facing = models.BooleanField(default=False, null=True, blank=True)
    as_a_service = models.CharField(max_length=80, choices=AS_SERVICE_CHOICES, null=True, blank=True)
    master_record = models.CharField(null=True, blank=True)
    is_kpi = models.BooleanField(default=False, null=True, blank=True)

    def calculate_is_kpi(self):
        """
        Evaluates the complex inclusion criteria against the Platform Configuration.
        """
        # Local import
        from configurations.models import PlatformConfiguration
        config = PlatformConfiguration.load()

        # 1. CIA: >= config_threshold OR 0 OR Null
        cia_valid = (
                self.cia_score is None or
                self.cia_score == 0 or
                self.cia_score >= config.kpi_min_cia
        )

        # 2. Internet Facing: False OR Null
        internet_valid = self.internet_facing is None or self.internet_facing is False

        # 3. Stage: In valid_stages OR Null
        stage_valid = self.asset_stage is None or self.asset_stage in config.get_valid_stages()

        # 4. Type: In valid_types OR Null
        type_valid = self.asset_type is None or self.asset_type in config.get_valid_types()

        # 5. Master Record: Null OR Empty
        master_valid = not self.master_record or str(self.master_record).strip() == ""

        # 6. As a Service: In valid_aas OR Null
        aas_valid = self.as_a_service is None or self.as_a_service in config.get_valid_aas()

        # ALL criteria must be met
        return all([
            cia_valid,
            internet_valid,
            stage_valid,
            type_valid,
            master_valid,
            aas_valid
        ])

    def save(self, *args, **kwargs):
        # Dynamically auto-calculate KPI status before saving to the database
        self.is_kpi = self.calculate_is_kpi()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ID", "organization", "name"], name="uniq_asset_per_org")
        ]

    def __str__(self):
        return f"{self.organization} / {self.name}"
