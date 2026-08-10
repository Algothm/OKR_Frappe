from __future__ import annotations

import frappe
from frappe.desk.desktop import get_workspace_sidebar_items as _get_workspace_sidebar_items


ROOT_WORKSPACE = "OKR Management"
ADMIN_WORKSPACES = {"Admin Workspace", "OKR Plan Planning", "OKR Sprint Planning"}
USER_WORKSPACES = {"OKR Workspace", "OKR Objective Execution", "OKR Key Result Execution", "Action Item", "Check-In"}


@frappe.whitelist()
def get_workspace_sidebar_items():
    result = _get_workspace_sidebar_items()
    is_administrator = frappe.session.user == "Administrator"
    hidden = USER_WORKSPACES if is_administrator else ADMIN_WORKSPACES
    allowed = ADMIN_WORKSPACES if is_administrator else USER_WORKSPACES

    if is_administrator:
        existing = {page.get("name") for page in result.get("pages", [])}
        missing = ADMIN_WORKSPACES - existing
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
        or (page.get("name") in allowed and page.get("name") not in hidden)
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
