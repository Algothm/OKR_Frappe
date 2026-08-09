import frappe


WORKSPACES = {
    "Admin Workspace": ("Admin Workspace", ""),
    "OKR Plan Planning": ("OKR Plan", "Admin Workspace"),
    "OKR Workspace": ("OKR Workspace", ""),
    "OKR Objective Execution": ("OKR Objective", "OKR Workspace"),
    "OKR Key Result Execution": ("OKR Key Result", "OKR Workspace"),
    "OKR Action Item Execution": ("OKR Action Item", "OKR Workspace"),
    "Check-In": ("OKR Check In", "OKR Workspace"),
}


def execute() -> None:
    for name, (title, parent_page) in WORKSPACES.items():
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value(
                "Workspace", name,
                {"title": title, "label": title, "parent_page": parent_page, "is_hidden": 0},
                update_modified=False,
            )
    frappe.clear_cache()

