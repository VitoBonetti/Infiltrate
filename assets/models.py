from django.db import models
import uuid as _uuid
from indicators.models import Tags, Flags


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
        ('None of the above', 'None of the above'),
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
    internet_facing = models.BooleanField(null=True, blank=True)
    as_a_service = models.CharField(max_length=80, choices=AS_SERVICE_CHOICES, null=True, blank=True)
    master_record = models.CharField(null=True, blank=True)
    is_kpi = models.BooleanField(default=False)
    is_pentest_queue = models.BooleanField(default=False)
    is_critical_app = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tags, blank=True, related_name='asset_tags')
    flags = models.ManyToManyField(Flags, blank=True, related_name='asset_flags')

    def calculate_is_kpi(self):
        """
        Evaluates the KPI criteria against Platform Configuration,
        while safely handling Pandas 'nan' and empty values.
        """
        from configurations.models import PlatformConfiguration
        config = PlatformConfiguration.load()

        # 1. Type: Must match valid_types (We do NOT allow empty here based on your rules)
        current_type = str(self.asset_type).strip().lower() if self.asset_type else ""
        type_valid = current_type in config.get_valid_types()

        # 2. Stage: Match valid_stages OR empty/nan
        current_stage = str(self.asset_stage).strip().lower() if self.asset_stage else ""
        stage_valid = not current_stage or current_stage in ['nan',
                                                             'none'] or current_stage in config.get_valid_stages()

        # 3. CIA: >= config_threshold OR 0 OR Null
        cia_valid = (
                self.cia_score is None or
                self.cia_score == 0 or
                self.cia_score >= config.kpi_min_cia
        )

        # 4. Internet Facing: True OR Null
        internet_valid = self.internet_facing is None or self.internet_facing is True

        # 5. As a Service: Match valid_aas OR empty/nan
        current_aas = str(self.as_a_service).strip().lower() if self.as_a_service else ""
        aas_valid = not current_aas or current_aas in ['nan', 'none'] or current_aas in config.get_valid_aas()

        # 6. Master Record: Null OR Empty/nan
        current_master = str(self.master_record).strip().lower() if self.master_record else ""
        master_valid = not current_master or current_master in ['nan', 'none']

        results = {
            "CIA": cia_valid,
            "Internet": internet_valid,
            "Stage": stage_valid,
            "Type": type_valid,
            "Master": master_valid,
            "AAS": aas_valid
        }

        if not all(results.values()):
            print(f"Asset {self.name} failed KPI: {results}")

        return all(results.values())


    def calculate_critical_app(self):
        from configurations.models import PlatformConfiguration
        config = PlatformConfiguration.load()

        if self.is_kpi:
            if self.cia_score >= config.cia_critical_app:
                return True
            return False
        return False


    def save(self, *args, **kwargs):
        # check if the asset is new
        is_new_asset = self._state.adding

        # Dynamically auto-calculate KPI status before saving to the database
        self.is_kpi = self.calculate_is_kpi()

        # If it's a new asset and in KPI, set pentest queue to True
        if is_new_asset and self.is_kpi:
            self.is_pentest_queue = True

        self.is_critical_app = self.calculate_critical_app()



        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'is_kpi'}

        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ID", "organization", "name"], name="uniq_asset_per_org")
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.market.code})"
