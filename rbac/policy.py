from django.contrib.contenttypes.models import ContentType
from rbac.models import RoleAssignment, ROLE_REGIONAL_VIEWER, ROLE_MANAGER, ROLE_OPERATOR
from rbac.scoping import get_region_for_scope_any, get_market_for_scope_any
from markets.models import Market
from regions.models import Regions
from organizations.models import Organization
from assets.models import Asset
from tests.models import Test
from vulns.models import Vulnerability

def is_god(user) -> bool:
    return bool(user and user.is_authenticated and user.is_superuser)


def is_admin(user) -> bool:
    return bool(user and user.is_authenticated and getattr(user, "is_platform_admin", False))

def is_pentester(user) -> bool:
    return bool(user and user.is_authenticated and getattr(user, "is_pentester", False))


def _has_assignment(user, role, obj) -> bool:
    ct = ContentType.objects.get_for_model(obj.__class__)
    return RoleAssignment.objects.filter(user=user, role=role, scope_content_type=ct, scope_object_id=obj.id).exists()


def user_is_manager_of_market(user, market: Market) -> bool:
    if is_god(user) or is_admin(user):
        return True
    return _has_assignment(user, ROLE_MANAGER, market)


def user_is_regional_viewer(user, region: Regions) -> bool:
    if is_god(user) or is_admin(user):
        return True
    return _has_assignment(user, ROLE_REGIONAL_VIEWER, region)


def user_is_operator_on(user, obj) -> bool:
    if is_god(user) or is_admin(user):
        return True
    return _has_assignment(user, ROLE_OPERATOR, obj)




def can_view(user, obj) -> bool:
    """
    Read access:
    - GOD/Admin: all
    - Regional Viewer: everything inside region
    - Manager: everything inside their market(s)
    - Operator: their scoped objects, plus "children" visibility
    """
    if is_god(user) or is_admin(user):
        return True
    if not user or not user.is_authenticated:
        return False

    if is_pentester(user):
        return isinstance(obj, (Test, Vulnerability))

    # Normalize vuln -> test for permission checks
    if isinstance(obj, Vulnerability):
        obj = obj.test

    # Regional viewer grants read within region
    region = get_region_for_scope_any(obj)
    if user_is_regional_viewer(user, region):
        return True

    # Manager grants read within market
    try:
        market = get_market_for_scope_any(obj)
        if user_is_manager_of_market(user, market):
            return True
    except Exception:
        pass

    # Operator exact scope or inherited scope
    if _operator_inherited_view(user, obj): return True

    return False

def _operator_inherited_view(user, obj) -> bool:
    """
    Operator inheritance rules:
    - Operator on Organization => can view org + its assets + tests on those assets + vulns
    - Operator on Asset => can view asset + tests including that asset + vulns
    - Operator on Test => can view test + its vulns
    """
    # exact scope
    if user_is_operator_on(user, obj):
        return True

    # if obj is Asset: check operator on its Organization
    if isinstance(obj, Asset):
        return user_is_operator_on(user, obj.organization)

    # if obj is Test: operator on any included Asset or their Organization
    if isinstance(obj, Test):
        assets = obj.assets.select_related("organization").all()
        for a in assets:
            if user_is_operator_on(user, a) or user_is_operator_on(user, a.organization):
                return True
        return False

    # if obj is Organization: nothing else to inherit upward
    if isinstance(obj, Organization):
        return False

    # Market/Region (operators not scoped there)
    return False

def can_manage_market(user, market: Market) -> bool:
    """
    "Manage" = invite/assign roles inside market.
    """
    return user_is_manager_of_market(user, market)

def can_edit(user, obj) -> bool:
    """
    Write access (example policy):
    - GOD/Admin: all
    - Manager: can edit inside their market (org/assets/tests/vulns)
    - Operator: can edit tests/vulns they are assigned to (or via asset/org inheritance)
    - Regional viewer: never
    """
    if is_god(user) or is_admin(user):
        return True
    if not user or not user.is_authenticated:
        return False
    if is_pentester(user):
        return isinstance(obj, (Test, Vulnerability))

    # Regional viewer never edits
    region = get_region_for_scope_any(obj)
    if user_is_regional_viewer(user, region):
        return False

    # Manager can edit within market
    try:
        market = get_market_for_scope_any(obj)
        if user_is_manager_of_market(user, market):
            return True
    except Exception:
        pass

    # Operator: allow edit only for Test/Vuln (common workflow)
    if isinstance(obj, Vulnerability):
        return can_edit(user, obj.test)

    if isinstance(obj, Test):
        return _operator_inherited_view(user, obj)

    return False