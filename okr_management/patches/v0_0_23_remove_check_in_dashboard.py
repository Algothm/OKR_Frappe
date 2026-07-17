import frappe


def execute():
    if frappe.db.exists("Page", "check-in"):
        frappe.delete_doc("Page", "check-in", force=True, ignore_permissions=True)

    if frappe.db.exists("Workspace", "Check-In"):
        frappe.db.set_value("Workspace", "Check-In", "title", "OKR Check In", update_modified=False)

    frappe.clear_cache()
