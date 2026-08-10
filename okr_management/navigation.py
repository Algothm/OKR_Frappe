from __future__ import annotations

import frappe
from frappe.desk.desktop import get_workspace_sidebar_items as _get_workspace_sidebar_items


ROOT_WORKSPACE = "OKR Management"
ADMIN_WORKSPACES = {"Admin Workspace", "OKR Plan Planning", "OKR Sprint Planning"}
USER_WORKSPACES = {"OKR Workspace"}


@frappe.whitelist()
def get_workspace_sidebar_items():
    result = _get_workspace_sidebar_items()
    is_administrator = frappe.session.user == "Administrator"
    hidden = USER_WORKSPACES if is_administrator else ADMIN_WORKSPACES
    allowed = ADMIN_WORKSPACES if is_administrator else USER_WORKSPACES

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
    }
    for page in result["pages"]:
        page["route"] = routes.get(page.get("name"), "")
    return result
