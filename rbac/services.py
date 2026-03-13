from django.core.exceptions import ValidationError
from django.db import transaction
from rbac.models import RoleAssignment, ROLE_MANAGER, ROLE_OPERATOR, ROLE_REGIONAL_VIEWER
from rbac.scoping import get_region_for_scope_any

@transaction.atomic
def assign_role(user, role, scope):
    if user.is_superuser:
        raise ValidationError("GOD cannot receive scoped roles.")
    if getattr(user, "is_platform_admin", False):
        raise ValidationError("Admin cannot receive scoped roles.")
    if getattr(user, "is_pentester", False):
        raise ValidationError("Pentester cannot receive scoped roles.")

    # Remove conflicts in same region (non-viewer)
    if role in {ROLE_MANAGER, ROLE_OPERATOR}:
        new_region = get_region_for_scope_any(scope)

        conflicts = RoleAssignment.objects.filter(user=user).exclude(role=ROLE_REGIONAL_VIEWER)
        delete_ids = []

        for ra in conflicts:
            try:
                ra_region = get_region_for_scope_any(ra.scope)
            except Exception:
                continue

            if ra_region.id != new_region.id:
                continue

            if (role == ROLE_MANAGER and ra.role == ROLE_OPERATOR) or (role == ROLE_OPERATOR and ra.role == ROLE_MANAGER):
                delete_ids.append(ra.id)

        if delete_ids:
            RoleAssignment.objects.filter(id__in=delete_ids).delete()

    ra = RoleAssignment(user=user, role=role)
    ra.scope = scope
    ra.full_clean()
    ra.save()
    return ra

@transaction.atomic
def remove_role(user, role, scope):
    # remove exact assignment
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(scope.__class__)
    RoleAssignment.objects.filter(user=user, role=role, scope_content_type=ct, scope_object_id=scope.id).delete()