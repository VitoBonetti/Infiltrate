from rbac.policy import is_god, is_admin

def can_access_management(user) -> bool:
    return is_god(user) or is_admin(user)

def admin_can_write(user) -> bool:
    """
    Decide what Admin can do in management.
    Example policy:
    - GOD: full CRUD
    - Admin: can view + create + update, but cannot delete
    """
    if is_god(user):
        return True
    if is_admin(user):
        return True
    return False

def admin_can_delete(user) -> bool:
    return is_god(user)  # Admin cannot delete