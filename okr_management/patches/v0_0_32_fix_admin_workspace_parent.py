import frappe


def execute() -> None:
    if frappe.db.exists("Workspace", "OKR Plan Planning"):
        frappe.db.set_value(
            "Workspace", "OKR Plan Planning",
            {"parent_page": "OKR Admin Workspace", "title": "Plan", "label": "Plan", "is_hidden": 0},
            update_modified=False,
        )
    frappe.clear_cache()
