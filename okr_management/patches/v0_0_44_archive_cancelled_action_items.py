import frappe


def execute():
    frappe.db.set_value(
        "OKR Action Item",
        {"status": "Cancelled"},
        "status",
        "Archived",
        update_modified=False,
    )