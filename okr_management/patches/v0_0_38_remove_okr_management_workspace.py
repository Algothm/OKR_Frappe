import frappe


def execute() -> None:
    for name in ("Admin Workspace", "OKR Workspace"):
        if frappe.db.exists("Workspace", name):
            frappe.db.set_value(
                "Workspace", name, "parent_page", "", update_modified=False
            )
    if frappe.db.exists("Workspace", "OKR Management"):
        frappe.delete_doc("Workspace", "OKR Management", force=True, ignore_permissions=True)
    frappe.clear_cache()

