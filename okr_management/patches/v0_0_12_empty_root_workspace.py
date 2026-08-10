import frappe


ROOT_WORKSPACE = "OKR Management"


def execute():
	if not frappe.db.exists("Workspace", ROOT_WORKSPACE):
		return

	workspace = frappe.get_doc("Workspace", ROOT_WORKSPACE)
	workspace.content = "[]"
	workspace.set("links", [])
	workspace.set("shortcuts", [])
	workspace.set("charts", [])
	workspace.set("number_cards", [])
	workspace.set("quick_lists", [])
	workspace.set("custom_blocks", [])
	workspace.flags.ignore_permissions = True
	workspace.save(ignore_permissions=True)
	frappe.clear_cache()
