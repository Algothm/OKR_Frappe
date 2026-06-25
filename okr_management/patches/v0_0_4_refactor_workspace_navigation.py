import frappe


def execute():
    stale_workspaces = ["Executive", "Review", "Reports", "Settings"]
    for name in stale_workspaces:
        if not frappe.db.exists("Workspace", name):
            continue
        parent_page, module = frappe.db.get_value("Workspace", name, ["parent_page", "module"])
        if parent_page == "OKR Management" and module == "OKR Management":
            frappe.delete_doc("Workspace", name, force=True, ignore_permissions=True)
    frappe.clear_cache()
