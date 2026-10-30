import frappe


def execute():
    """Use standard admin-only delete permissions, including on existing sites."""
    for doctype, module_name in (
        ("OKR Check In", "okr_check_in"),
        ("OKR Objective", "okr_objective"),
    ):
        frappe.reload_doc("okr_management", "doctype", module_name)
        frappe.db.delete("Custom DocPerm", {"parent": doctype})
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache()
