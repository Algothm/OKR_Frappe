import frappe


def execute() -> None:
    frappe.reload_doc("okr_management", "page", "okr_workspace")
    frappe.clear_cache()

