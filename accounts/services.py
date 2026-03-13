from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import Invite, User
from rbac.policy import is_god, is_admin, user_is_manager_of_market
from rbac.services import assign_role
from rbac.models import ROLE_OPERATOR, ROLE_REGIONAL_VIEWER, ROLE_MANAGER
from django.contrib.auth.hashers import make_password
import secrets


def create_invite(actor: User, email: str, expires_days: int = 7) -> Invite:
    if not actor.is_authenticated:
        raise ValidationError("Authentication required.")
    # Allowed inviters: GOD/Admin/Manager (you can tighten this)
    if not (is_god(actor) or is_admin(actor) or actor.role_assignments.filter(role=ROLE_MANAGER).exists()):
        raise ValidationError("You are not allowed to invite users.")

    raw_token = secrets.token_urlsafe(32)
    hashed_token = make_password(raw_token)

    invite = Invite(
        email=email,
        invited_by=actor,
        token_hash=hashed_token,
        expires_at=timezone.now() + timezone.timedelta(days=expires_days),
    )
    invite.full_clean()
    invite.save()

    return invite, raw_token

def accept_invite(raw_token: str, username: str, password: str, email: str) -> User:

    try:
        invite = Invite.objects.get(email=email, used_at__isnull=True)
    except Invite.DoesNotExist:
        raise ValidationError("Invalid or already used invite.")

    if not invite.verify_token(raw_token):
        raise ValidationError("Invalid invite token.")
    if invite.is_expired:
        raise ValidationError("Invite expired.")

    user = User(username=username, email=invite.email)
    user.set_password(password)
    user.full_clean()
    user.save()

    invite.used_at = timezone.now()
    invite.save(update_fields=["used_at"])
    return user

def manager_assign_operator(actor: User, target_user: User, scope_obj):
    """
    Manager can assign OPERATOR only within markets they manage.
    scope_obj can be Organization/Asset/Test (operator scopes).
    """
    if is_god(actor) or is_admin(actor):
        return assign_role(target_user, ROLE_OPERATOR, scope_obj)

    market = _resolve_market(scope_obj)

    if not user_is_manager_of_market(actor, market):
        raise ValidationError("Manager can only assign inside markets they manage.")

    return assign_role(target_user, ROLE_OPERATOR, scope_obj)

def _resolve_market(scope_obj):
    # local import to avoid circulars
    from rbac.scoping import get_market_for_scope_any
    return get_market_for_scope_any(scope_obj)