from django import template
from rbac.policy import can_view, can_edit, is_god, is_admin, is_pentester

register = template.Library()

@register.simple_tag(takes_context=True)
def gp_is_god(context):
    return is_god(context["request"].user)

@register.simple_tag(takes_context=True)
def gp_is_admin(context):
    return is_admin(context["request"].user)

@register.simple_tag(takes_context=True)
def gp_is_pentester(context):
    return is_pentester(context["request"].user)

@register.simple_tag(takes_context=True)
def gp_has_scoped_role(context, role: str) -> bool:
    """
    True if user has at least one assignment for that role anywhere.
    Useful for showing menu sections.
    """
    u = context["request"].user
    if not u.is_authenticated:
        return False
    if is_god(u) or is_admin(u):
        return True
    return u.role_assignments.filter(role=role).exists()

@register.simple_tag(takes_context=True)
def gp_has_any_role(context) -> bool:
    u = context["request"].user
    if not u.is_authenticated:
        return False
    if is_god(u) or is_admin(u) or is_pentester(u):
        return True
    return u.role_assignments.exists()