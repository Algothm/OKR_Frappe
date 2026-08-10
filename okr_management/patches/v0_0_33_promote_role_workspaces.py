import frappe


def execute() -> None:
    frappe.reload_doc("okr_management", "workspace", "admin_workspace")
    frappe.reload_doc("okr_management", "workspace", "okr_workspace")
    for name in ("Admin Workspace", "OKR Workspace"):
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value(
                "Workspace", name, "parent_page", "", update_modified=False
            )
    frappe.clear_cache()
