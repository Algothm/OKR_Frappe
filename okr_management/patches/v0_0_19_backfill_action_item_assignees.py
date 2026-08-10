import frappe


def execute():
    if not frappe.db.table_exists("OKR Action Item Assignee"):
        return

    action_items = frappe.get_all(
        "OKR Action Item",
        filters={"owner_user": ["is", "set"]},
        fields=["name", "owner_user"],
    )
    for action_item in action_items:
        if frappe.db.exists(
            "OKR Action Item Assignee",
            {"parent": action_item.name, "parenttype": "OKR Action Item"},
        ):
            continue

        employee = frappe.db.get_value(
            "Employee",
            {"user_id": action_item.owner_user, "status": "Active"},
            "name",
        )
        if employee:
            frappe.get_doc({
                "doctype": "OKR Action Item Assignee",
                "parent": action_item.name,
                "parenttype": "OKR Action Item",
                "parentfield": "assignees",
                "employee": employee,
            }).db_insert()
