from __future__ import annotations

import frappe


TEST_USERS = (
    "utsav@algothm.com",
    "acc2@ajantabottle.com",
    "prince@algothm.com",
)
ADMIN_ROLES = ("System Manager", "OKR Admin")


def _remove_admin_roles(user: str) -> None:
    frappe.db.delete(
        "Has Role",
        {"parent": user, "parenttype": "User", "parentfield": "roles", "role": ["in", ADMIN_ROLES]},
    )
    if not frappe.db.exists(
        "Has Role",
        {"parent": user, "parenttype": "User", "parentfield": "roles", "role": "OKR User"},
    ):
        role = frappe.new_doc("Has Role")
        role.update({"parent": user, "parenttype": "User", "parentfield": "roles", "role": "OKR User"})
        role.db_insert()


def execute() -> None:
    frappe.reload_doc("okr_management", "workspace", "admin_workspace")

    if frappe.db.exists("Workspace", "Admin Workspace"):
        frappe.db.set_value(
            "Workspace", "Admin Workspace",
            {"label": "OKR Admin Workspace", "title": "OKR Admin Workspace"},
            update_modified=False,
        )

    if frappe.db.exists("Workspace", "OKR Plan Planning"):
        frappe.db.set_value(
            "Workspace", "OKR Plan Planning",
            {"label": "Plan", "title": "Plan", "parent_page": "Admin Workspace"},
            update_modified=False,
        )

    for user in TEST_USERS:
        if frappe.db.exists("User", user):
            _remove_admin_roles(user)
