import frappe

ALIASES = {
    "okr-admin-workspace": ("OKR Admin Workspace", ("All", "System Manager", "Desk User")),
    "plan": ("Plan", ("All", "System Manager", "Desk User")),
    "objective": ("Objective", ("All", "System Manager", "Desk User")),
    "key-result": ("Key Result", ("All", "System Manager", "Desk User")),
    "action-item": ("Action Item", ("All", "System Manager", "Desk User")),
    "check-in": ("Check-In", ("All", "System Manager", "Desk User")),
}


def execute() -> None:
    for page_name, (title, roles) in ALIASES.items():
        if not frappe.db.exists("Page", page_name):
            page = frappe.new_doc("Page")
            page.name = page_name
            page.page_name = page_name
            page.title = title
            page.module = "OKR Management"
            page.standard = "Yes"
            page.system_page = 0
            page.db_insert()
        else:
            frappe.db.set_value("Page", page_name, {"standard": "Yes", "title": title}, update_modified=False)

        frappe.db.delete(
            "Has Role", {"parent": page_name, "parenttype": "Page", "parentfield": "roles"}
        )
        for index, role_name in enumerate(roles, start=1):
            role = frappe.new_doc("Has Role")
            role.update({
                "parent": page_name,
                "parenttype": "Page",
                "parentfield": "roles",
                "idx": index,
                "role": role_name,
            })
            role.db_insert()

    frappe.clear_cache()
