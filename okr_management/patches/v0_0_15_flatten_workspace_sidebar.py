import frappe


ROOT_WORKSPACE = "OKR Management"

WORKSPACE_HIERARCHY = {
    "Admin Workspace": (ROOT_WORKSPACE, 2.0, "organization"),
    "OKR Plan Planning": ("Admin Workspace", 2.1, "clipboard"),
    "OKR Sprint Planning": ("Admin Workspace", 2.2, "project"),
    "OKR Workspace": (ROOT_WORKSPACE, 3.0, "dashboard"),
    "OKR Objective Execution": ("OKR Workspace", 3.1, "milestone"),
    "OKR Key Result Execution": ("OKR Workspace", 3.2, "chart"),
    "Check-In": ("OKR Workspace", 3.3, "solid-success"),
}

GROUPING_WORKSPACES = ("Planning", "Execution")


def execute():
    for name, (parent_page, sequence_id, icon) in WORKSPACE_HIERARCHY.items():
        if not frappe.db.exists("Workspace", name):
            continue

        frappe.db.set_value(
            "Workspace",
            name,
            {"parent_page": parent_page, "sequence_id": sequence_id, "icon": icon},
            update_modified=False,
        )

    for name in GROUPING_WORKSPACES:
        if frappe.db.exists("Workspace", name):
            frappe.delete_doc("Workspace", name, force=True, ignore_permissions=True)

    frappe.clear_cache()
