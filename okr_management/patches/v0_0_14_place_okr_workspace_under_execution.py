import frappe


def execute():
    if not frappe.db.exists("Workspace", "OKR Workspace"):
        return

    frappe.db.set_value(
        "Workspace",
        "OKR Workspace",
        {
            "parent_page": "Execution",
            "sequence_id": 3.1,
        },
        update_modified=False,
    )
    frappe.clear_cache()