import frappe


ALIASES = {
    "okr-admin-workspace": ("OKR Admin Workspace", ("System Manager", "OKR Admin")),
    "plan": ("Plan", ("System Manager", "OKR Admin")),
    "objective": ("Objective", ("Desk User",)),
    "key-result": ("Key Result", ("Desk User",)),
    "action-item": ("Action Item", ("Desk User",)),
    "check-in": ("Check-In", ("Desk User",)),
}


def execute() -> None:
    for page_name, (title, roles) in ALIASES.items():
        if not frappe.db.exists("Page", page_name):
            page = frappe.new_doc("Page")
            page.name = page_name
            page.page_name = page_name
            page.title = title
            page.module = "OKR Management"
            page.standard = "No"
            page.system_page = 0
            page.db_insert()

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
    for user in (
        "Administrator",
        "utsav@algothm.com",
        "acc2@ajantabottle.com",
        "prince@algothm.com",
    ):
        frappe.cache.delete_value("has_role:Page", user=user)