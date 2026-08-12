import frappe


CHILD_WORKSPACES = {
    "OKR Plan Planning": ("Plan", "Admin Workspace"),
    "OKR Objective Execution": ("Objective", "OKR Workspace"),
    "OKR Key Result Execution": ("Key Result", "OKR Workspace"),
    "OKR Action Item Execution": ("Action Item", "OKR Workspace"),
    "Check-In": ("Check-In", "OKR Workspace"),
}


def execute() -> None:
    for name, (title, parent_page) in CHILD_WORKSPACES.items():
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value(
                "Workspace",
                name,
                {"title": title, "label": title, "parent_page": parent_page, "is_hidden": 0},
                update_modified=False,
            )
    frappe.clear_cache()

