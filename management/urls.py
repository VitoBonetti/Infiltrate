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
    path('regions/', RegionView.as_view(), name='regions'),
    path('markets/', MarketListView.as_view(), name='markets'),
    path('markets/form/', MarketFormView.as_view(), name='market_form'),
    path('organizations/', OrganizationListView.as_view(), name='organizations'),
    path('organizations/form/', OrganizationFormView.as_view(), name='organization_form'),
    path('users/', UserListView.as_view(), name='users'),
    path('users/form/', UserFormView.as_view(), name='user_form'),
    path('users/<uuid:user_id>/roles/', UserRoleView.as_view(), name='user_roles'),
    path('assets/', AssetListView.as_view(), name='assets'),
    path('assets/form/', AssetFormView.as_view(), name='asset_form'),
    path("configuration/", ConfigurationUpdateView.as_view(), name="configuration_settings"),
    path('tags/', TagsView.as_view(), name='indicator_tags'),
    path('flags/', FlagsView.as_view(), name='indicator_flags'),
    path('indicators/', IndicatorsView.as_view(), name='indicators'),
]