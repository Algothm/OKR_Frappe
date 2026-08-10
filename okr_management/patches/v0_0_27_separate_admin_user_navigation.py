from __future__ import annotations

import frappe


ADMIN_ROLES = ("System Manager", "OKR Admin")
ADMIN_WORKSPACES = ("Admin Workspace", "OKR Plan Planning", "OKR Sprint Planning")
USER_PAGE_ROLES = ("All",)
USER_LEAF_WORKSPACES = (
    "OKR Objective Execution",
    "OKR Key Result Execution",
    "OKR Action Item Execution",
    "Check-In",
)


def _set_roles(parent: str, parenttype: str, roles=ADMIN_ROLES) -> None:
    frappe.db.delete(
        "Has Role",
        {"parent": parent, "parenttype": parenttype, "parentfield": "roles"},
    )
    for index, role in enumerate(roles, start=1):
        row = frappe.new_doc("Has Role")
        row.update({
            "parent": parent,
            "parenttype": parenttype,
            "parentfield": "roles",
            "idx": index,
            "role": role,
        })
        row.db_insert()


def execute():
    frappe.reload_doc("okr_management", "page", "admin_workspace")
    frappe.reload_doc("okr_management", "page", "okr_workspace")
    frappe.reload_doc("okr_management", "workspace", "admin_workspace")
    _set_roles("admin-workspace", "Page")
    _set_roles("okr-workspace", "Page", USER_PAGE_ROLES)

    for name in ADMIN_WORKSPACES:
        if frappe.db.exists("Workspace", name):
            _set_roles(name, "Workspace")

    for name in USER_LEAF_WORKSPACES:
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)

    frappe.clear_cache()
