import frappe


def execute() -> None:
    frappe.reload_doc("okr_management", "workspace", "admin_workspace")
    frappe.reload_doc("okr_management", "workspace", "okr_plan_planning")

    if frappe.db.exists("Workspace", "Admin Workspace"):
        frappe.db.set_value(
            "Workspace",
            "Admin Workspace",
            {"public": 1, "parent_page": "", "is_hidden": 0},
            update_modified=False,
        )

    if frappe.db.exists("Workspace", "OKR Plan Planning"):
        frappe.db.set_value(
            "Workspace",
            "OKR Plan Planning",
            {
                "public": 1,
                "parent_page": "OKR Admin Workspace",
                "is_hidden": 0,
                "title": "Plan",
                "label": "Plan",
            },
            update_modified=False,
        )

    frappe.clear_cache()
