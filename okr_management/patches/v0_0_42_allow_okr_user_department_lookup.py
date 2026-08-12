import frappe


def execute() -> None:
    """Allow OKR users to resolve Department links used by Check-In context."""
    filters = {
        "parent": "Department",
        "role": "OKR User",
        "permlevel": 0,
    }
    name = frappe.db.exists("Custom DocPerm", filters)
    permission = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
    permission.update(filters)
    permission.read = 1
    permission.select = 1

    if permission.is_new():
        permission.insert(ignore_permissions=True)
    else:
        permission.save(ignore_permissions=True)

    frappe.clear_cache()
