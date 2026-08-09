import frappe


def execute() -> None:
    frappe.reload_doc("okr_management", "page", "okr_workspace")
    frappe.db.delete(
        "Has Role", {"parent": "okr-workspace", "parenttype": "Page", "parentfield": "roles"}
    )
    frappe.clear_cache()
