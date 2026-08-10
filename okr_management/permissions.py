from __future__ import annotations

import frappe


def get_plan_permission_query_conditions(user: str | None = None) -> str:
    """Expose OKR Plans only to the built-in Administrator account."""
    return "" if (user or frappe.session.user) == "Administrator" else "1=0"


def has_plan_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
    """Enforce Administrator-only Plan access for document and direct-link checks."""
    return (user or frappe.session.user) == "Administrator"
