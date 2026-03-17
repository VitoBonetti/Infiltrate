from django.urls import path
from management.views import (
    ManagementHomeView,
    RegionView,
    MarketListView,
    MarketFormView,
    OrganizationListView,
    OrganizationFormView,
    UserListView,
    UserFormView,
    UserRoleView,
    AssetListView,
    AssetFormView,
    ConfigurationUpdateView,
    TagsView,
    IndicatorsView, FlagsView
)

urlpatterns = [
    path('', ManagementHomeView.as_view(), name='management'),
    path('mng_regions/', RegionView.as_view(), name='mng_regions'),
    path('mng_markets/', MarketListView.as_view(), name='mng_markets'),
    path('mng_markets/form/', MarketFormView.as_view(), name='mng_market_form'),
    path('mng_organizations/', OrganizationListView.as_view(), name='mng_organizations'),
    path('mng_organizations/form/', OrganizationFormView.as_view(), name='mng_organization_form'),
    path('mng_users/', UserListView.as_view(), name='mng_users'),
    path('mng_users/form/', UserFormView.as_view(), name='mng_user_form'),
    path('mng_users/<uuid:user_id>/roles/', UserRoleView.as_view(), name='mng_user_roles'),
    path('mng_assets/', AssetListView.as_view(), name='mng_assets'),
    path('mng_assets/form/', AssetFormView.as_view(), name='mng_asset_form'),
    path("mng_configuration/", ConfigurationUpdateView.as_view(), name="configuration_settings"),
    path('mng_tags/', TagsView.as_view(), name='indicator_tags'),
    path('mng_flags/', FlagsView.as_view(), name='indicator_flags'),
    path('mng_indicators/', IndicatorsView.as_view(), name='indicators'),
]