from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rbac.policy import is_god, is_admin
from rbac.models import ROLE_MANAGER, ROLE_OPERATOR, ROLE_REGIONAL_VIEWER


@login_required
def dashboard(request):
    u = request.user

    if is_god(u):
        role_text = "You are GOD."
    elif is_admin(u):
        role_text = "You are Admin."
    elif getattr(u, "is_pentester", False):
        role_text = "You are Pentester."
    else:
        # With explicit scope fields, we can select_related all possible FK scopes
        ras = (
            u.role_assignments
            .select_related("region", "market", "organization", "asset", "test")
            .all()
        )

        if not ras.exists():
            role_text = "You have no scoped roles yet."
        else:
            lines = []
            for ra in ras:
                scope = ra.get_scope()  # returns Region/Market/Org/Asset/Test
                scope_label = str(scope) if scope else "NO_SCOPE"

                if ra.role == ROLE_REGIONAL_VIEWER:
                    lines.append(f"Regional Viewer on {scope_label}")
                elif ra.role == ROLE_MANAGER:
                    lines.append(f"Manager on {scope_label}")
                elif ra.role == ROLE_OPERATOR:
                    lines.append(f"Operator on {scope_label}")

            role_text = " / ".join(lines)

    return render(request, "dashboard/dashboard.html", {"role_text": role_text})