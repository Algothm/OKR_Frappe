from __future__ import annotations

import frappe
from frappe.desk.desktop import get_workspace_sidebar_items as _get_workspace_sidebar_items

ADMIN_WORKSPACES = {"Admin Workspace", "OKR Plan Planning", "OKR Sprint Planning"}
USER_WORKSPACES = {"OKR Workspace", "OKR Objective Execution", "OKR Key Result Execution", "Action Item", "Check-In"}


@frappe.whitelist()
def get_workspace_sidebar_items():
    result = _get_workspace_sidebar_items()
    roles = set(frappe.get_roles())
    admin_user = frappe.session.user == "Administrator" or "OKR Admin" in roles
    okr_user = "OKR User" in roles

    if admin_user and okr_user:
        allowed = ADMIN_WORKSPACES | USER_WORKSPACES
    elif admin_user:
        allowed = ADMIN_WORKSPACES
    elif okr_user:
        allowed = USER_WORKSPACES
    else:
        allowed = set()

    existing = {page.get("name") for page in result.get("pages", [])}
    missing = allowed - existing
    if missing:
        result.setdefault("pages", []).extend(
            frappe.get_all(
                "Workspace",
                filters={"name": ["in", sorted(missing)]},
                fields=[
                    "name", "title", "for_user", "parent_page", "content", "public",
                    "module", "icon", "indicator_color", "is_hidden", "label",
                ],
            )
        )

    result["pages"] = [
        page
        for page in result.get("pages", [])
        if page.get("module") != "OKR Management"
        or page.get("name") in allowed
    ]
    routes = {
        "Admin Workspace": "admin-workspace",
        "OKR Plan Planning": "okr-plan",
        "OKR Workspace": "okr-workspace",
        "OKR Objective Execution": "okr-objective",
        "OKR Key Result Execution": "okr-key-result",
        "Action Item": "okr-action-item",
        "Check-In": "okr-check-in",
    }
    for page in result["pages"]:
        page["route"] = routes.get(page.get("name"), "")
    return result
