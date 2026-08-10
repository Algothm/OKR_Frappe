import frappe


USER_DOCTYPES = (
    "OKR Objective",
    "OKR Key Result",
    "OKR Action Item",
    "OKR Check In",
)


def execute() -> None:
    if not frappe.db.exists("Role", "OKR User"):
        frappe.get_doc({"doctype": "Role", "role_name": "OKR User", "desk_access": 1}).insert(
            ignore_permissions=True
        )

    for doctype in USER_DOCTYPES:
        filters = {"parent": doctype, "role": "OKR User", "permlevel": 0}
        name = frappe.db.exists("Custom DocPerm", filters)
        if name:
            permission = frappe.get_doc("Custom DocPerm", name)
        else:
            permission = frappe.new_doc("Custom DocPerm")
            permission.update(filters)
        permission.read = 1
        permission.write = 1
        permission.create = 1
        permission.select = 1
        if permission.is_new():
            permission.insert(ignore_permissions=True)
        else:
            permission.save(ignore_permissions=True)

    frappe.clear_cache()
