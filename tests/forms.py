from django import forms
from tests.models import Test
from assets.models import Asset
from rbac.models import RoleAssignment, ROLE_MANAGER


class TestForm(forms.ModelForm):
    class Meta:
        model = Test
        # Excluded automated fields: start_date, end_date, quarter, requested_by
        fields = ['name', 'assets', 'service', 'proposal_date', 'ritm', 'status', 'tags', 'flags', 'description']
        widgets = {
            'proposal_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            is_global_role = self.user.is_superuser or getattr(self.user, 'is_platform_admin', False) or getattr(
                self.user, 'is_pentester', False)

            if not is_global_role:
                # Remove status so managers can only submit 'Requested' by default
                if 'status' in self.fields:
                    self.fields.pop('status')

                # Restrict assets to the manager's market(s)
                manager_assignments = RoleAssignment.objects.filter(user=self.user, role=ROLE_MANAGER)
                market_ids = manager_assignments.values_list('market_id', flat=True)

                self.fields['assets'].queryset = Asset.objects.filter(
                    organization__market_id__in=market_ids
                )
            else:
                # Global roles see all assets
                self.fields['assets'].queryset = Asset.objects.all()