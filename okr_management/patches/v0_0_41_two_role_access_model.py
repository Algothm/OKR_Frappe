import frappe


def execute() -> None:
    for role_name in ("OKR Admin", "OKR User"):
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {"doctype": "Role", "role_name": role_name, "desk_access": 1}
            ).insert(ignore_permissions=True)

    frappe.reload_doc("okr_management", "doctype", "okr_plan")

    frappe.db.delete("Has Role", {"role": "OKR Manager"})
    frappe.db.delete("Custom DocPerm", {"role": "OKR Manager"})
    frappe.db.delete("DocPerm", {"role": "OKR Manager"})
    frappe.db.delete("Role", {"name": "OKR Manager"})

    frappe.clear_cache()
