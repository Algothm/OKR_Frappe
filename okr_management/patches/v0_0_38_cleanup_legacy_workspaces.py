import frappe


def execute():
	"""Idempotently clean up legacy OKR Management Workspace records."""
	legacy_workspaces = ["OKR Workspace", "Admin Workspace"]
	for ws_name in legacy_workspaces:
		if frappe.db.exists("Workspace", ws_name):
			doc_module = frappe.db.get_value("Workspace", ws_name, "module")
			if doc_module == "OKR Management":
				frappe.delete_doc("Workspace", ws_name, ignore_permissions=True, force=True)
