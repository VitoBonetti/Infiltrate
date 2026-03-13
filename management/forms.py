from django.forms import ModelForm, CheckboxInput
from regions.models import Regions
from markets.models import Market
from organizations.models import Organization
from accounts.models import User
from rbac.models import RoleAssignment
from assets.models import Asset
from configurations.models import PlatformConfiguration


class RegionsForm(ModelForm):
    class Meta:
        model = Regions
        fields = ['region', 'active']


class MarketForm(ModelForm):
    class Meta:
        model = Market
        fields = [
            'region', 'market', 'code', 'language',
            'active', 'key_market', 'description', 'flag_icons'
        ]


class OrganizationForm(ModelForm):
    class Meta:
        model = Organization
        fields = ['market', 'name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # show only the market name and force alphabetic order
        self.fields['market'].label_from_instance = lambda obj: obj.market
        self.fields['market'].queryset = Market.objects.filter(active=True).order_by('market')


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'is_active', 'is_platform_admin', 'is_pentester']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['first_name'].required = True
            self.fields['last_name'].required = True


class RoleAssignmentForm(ModelForm):
    class Meta:
        model = RoleAssignment
        fields = ['role', 'region', 'market', 'organization']

    def __init__(self, *args, **kwargs):
        self.user_instance = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # If a user was passed in, attach it to the underlying model instance
        if self.user_instance:
            self.instance.user = self.user_instance

        # Clean up dropdowns to show alphabetical order
        if 'region' in self.fields:
            self.fields['region'].queryset = self.fields['region'].queryset.order_by('region')
        if 'market' in self.fields:
            self.fields['market'].queryset = self.fields['market'].queryset.order_by('market')
            self.fields['market'].label_from_instance = lambda obj: obj.market
        if 'organization' in self.fields:
            self.fields['organization'].queryset = self.fields['organization'].queryset.order_by('name')


class AssetForm(ModelForm):
    class Meta:
        model = Asset
        exclude = ['uuid', 'is_kpi']
        widgets = {
            'internet_facing': CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'organization' in self.fields:
            self.fields['organization'].queryset = self.fields['organization'].queryset.order_by('name')
            self.fields['organization'].label_from_instance = lambda obj: f"{obj.name} ({obj.market.market})"


class ConfigurationForm(ModelForm):
    class Meta:
        model = PlatformConfiguration
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply the same styling you use for your other forms
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control form-control-sm border-1 border-dark rounded'