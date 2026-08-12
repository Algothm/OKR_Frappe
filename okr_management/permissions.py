from __future__ import annotations

import frappe


def is_okr_admin(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return user == "Administrator" or "OKR Admin" in frappe.get_roles(user)


def is_okr_user(user: str | None = None) -> bool:
    user = user or frappe.session.user
    return "OKR User" in frappe.get_roles(user)


def _is_plan_team_member(plan_name: str, user: str) -> bool:
    return bool(
        frappe.db.exists(
            "OKR Plan Team Member",
            {
                "parent": plan_name,
                "parenttype": "OKR Plan",
                "parentfield": "members",
                "member_user": user,
            },
        )
    )


def get_plan_permission_query_conditions(user: str | None = None) -> str:
    """Admins and OKR Users can read plans; plan mutations remain admin-only."""
    user = user or frappe.session.user
    if is_okr_admin(user) or is_okr_user(user):
        return ""
    return "1=0"


def has_plan_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
    """Plan management is admin-only; every OKR User receives read/select access."""
    user = user or frappe.session.user
    if is_okr_admin(user):
        return True
    if ptype not in {"read", "select"} or not is_okr_user(user):
        return False
    return True
