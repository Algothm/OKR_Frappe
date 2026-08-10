import frappe


def execute():
    obsolete_workspaces = {
        "OKR Plan": "Planning",
        "OKR Sprint": "Planning",
        "Objectives": "Execution",
        "Key Results": "Execution",
    }

    for name, parent_page in obsolete_workspaces.items():
        if not frappe.db.exists("Workspace", name):
            continue

        workspace_parent, module = frappe.db.get_value(
            "Workspace", name, ["parent_page", "module"]
        )
        if workspace_parent == parent_page and module == "OKR Management":
            frappe.delete_doc("Workspace", name, force=True, ignore_permissions=True)

    frappe.clear_cache()
