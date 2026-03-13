from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

ROLE_REGIONAL_VIEWER = "REGIONAL_VIEWER"
ROLE_MANAGER = "MANAGER"
ROLE_OPERATOR = "OPERATOR"

ROLE_CHOICES = [
    (ROLE_REGIONAL_VIEWER, "Regional Viewer"),
    (ROLE_MANAGER, "Manager"),
    (ROLE_OPERATOR, "Operator"),
]


class RoleAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)

    # Explicit scopes (exactly one must be set)
    region = models.ForeignKey(
        "regions.Regions", null=True, blank=True, on_delete=models.CASCADE, related_name="role_assignments"
    )
    market = models.ForeignKey(
        "markets.Market", null=True, blank=True, on_delete=models.CASCADE, related_name="role_assignments"
    )
    organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="role_assignments"
    )
    asset = models.ForeignKey(
        "assets.Asset", null=True, blank=True, on_delete=models.CASCADE, related_name="role_assignments"
    )
    test = models.ForeignKey(
        "tests.Test", null=True, blank=True, on_delete=models.CASCADE, related_name="role_assignments"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Prevent duplicates per scope type:
            models.UniqueConstraint(
                fields=["user", "role", "region"],
                name="uniq_role_region",
                condition=models.Q(region__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "role", "market"],
                name="uniq_role_market",
                condition=models.Q(market__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "role", "organization"],
                name="uniq_role_organization",
                condition=models.Q(organization__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "role", "asset"],
                name="uniq_role_asset",
                condition=models.Q(asset__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "role", "test"],
                name="uniq_role_test",
                condition=models.Q(test__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.role} - {self.scope_label}"

    @property
    def scope_label(self) -> str:
        scope = self.get_scope()
        return str(scope) if scope is not None else "NO_SCOPE"

    def get_scope(self):
        """
        Returns the actual scope object (Region/Market/Organization/Asset/Test).
        Exactly one should be set.
        """
        if self.region_id:
            return self.region
        if self.market_id:
            return self.market
        if self.organization_id:
            return self.organization
        if self.asset_id:
            return self.asset
        if self.test_id:
            return self.test
        return None

    def _scope_kind(self) -> str:
        if self.region_id:
            return "region"
        if self.market_id:
            return "market"
        if self.organization_id:
            return "organization"
        if self.asset_id:
            return "asset"
        if self.test_id:
            return "test"
        return "none"

    def clean(self):
        super().clean()

        # 0) GOD/Admin cannot have scoped roles
        if self.user and self.user.is_superuser:
            raise ValidationError("GOD (superuser) cannot have any other role assignments.")
        if self.user and getattr(self.user, "is_platform_admin", False):
            raise ValidationError("Admin cannot have any scoped role assignments.")
        if self.user and getattr(self.user, "is_pentester", False):
            raise ValidationError("Global Pentester cannot have any scoped role assignments.")

        # 1) Exactly one scope must be set
        scopes_set = [
            bool(self.region_id),
            bool(self.market_id),
            bool(self.organization_id),
            bool(self.asset_id),
            bool(self.test_id),
        ]
        if sum(scopes_set) != 1:
            raise ValidationError("Exactly one scope must be set: region OR market OR organization OR asset OR test.")

        kind = self._scope_kind()

        # 2) Role must match scope type
        if self.role == ROLE_REGIONAL_VIEWER and kind != "region":
            raise ValidationError("Regional Viewer must be scoped to a Region.")
        if self.role == ROLE_MANAGER and kind != "market":
            raise ValidationError("Manager must be scoped to a Market.")
        if self.role == ROLE_OPERATOR and kind not in {"organization", "asset", "test"}:
            raise ValidationError("Operator must be scoped to Organization, Asset, or Test.")

        # 3) Non-overlap rule:
        # cannot mix Manager and Operator within the same Region (Regional Viewer excluded).
        if self.role in {ROLE_MANAGER, ROLE_OPERATOR}:
            new_region = self._resolve_region_for_this_assignment()

            # Compare with existing assignments for this user (excluding this record)
            qs = RoleAssignment.objects.filter(user=self.user).exclude(pk=self.pk)
            qs = qs.exclude(role=ROLE_REGIONAL_VIEWER)

            for ra in qs:
                # only Manager/Operator are relevant here
                if ra.role not in {ROLE_MANAGER, ROLE_OPERATOR}:
                    continue

                try:
                    ra_region = ra._resolve_region_for_this_assignment()
                except Exception:
                    continue

                if ra_region.id != new_region.id:
                    continue

                # conflict if one is manager and the other is operator in same region
                if (self.role == ROLE_MANAGER and ra.role == ROLE_OPERATOR) or (
                    self.role == ROLE_OPERATOR and ra.role == ROLE_MANAGER
                ):
                    raise ValidationError("Cannot mix Manager and Operator roles within the same Region.")

    def _resolve_region_for_this_assignment(self):
        """
        Returns the Region associated with this assignment's scope.
        Uses the explicit scope FKs.
        """
        # region scope
        if self.region_id:
            return self.region

        # market scope
        if self.market_id:
            return self.market.region

        # organization scope
        if self.organization_id:
            return self.organization.market.region

        # asset scope
        if self.asset_id:
            return self.asset.organization.market.region

        # test scope (single-market rule via assets)
        if self.test_id:
            # Test must be single-market by design (enforced in tests app)
            assets = self.test.assets.select_related("organization__market__region").all()
            market_ids = {a.organization.market_id for a in assets}
            if not market_ids:
                raise ValidationError("Test has no assets; cannot determine region for role assignment.")
            if len(market_ids) > 1:
                raise ValidationError("Test spans multiple markets; forbidden by design.")
            return assets[0].organization.market.region

        raise ValidationError("No scope set; cannot resolve region.")