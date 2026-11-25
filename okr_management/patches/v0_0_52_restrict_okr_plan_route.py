from __future__ import annotations

import frappe


PLAN_WORKSPACE = "OKR Plan Planning"
PLAN_ROLES = ("OKR Admin", "System Manager")


def execute() -> None:
	if not frappe.db.exists("Workspace", PLAN_WORKSPACE):
		return

	frappe.db.delete(
		"Has Role",
		{"parent": PLAN_WORKSPACE, "parenttype": "Workspace", "parentfield": "roles"},
	)
	for index, role_name in enumerate(PLAN_ROLES, start=1):
		role = frappe.new_doc("Has Role")
		role.update(
		{
			"parent": PLAN_WORKSPACE,
			"parenttype": "Workspace",
			"parentfield": "roles",
			"idx": index,
			"role": role_name,
		}
		)
		role.db_insert()

	# This workspace was previously public with no roles and may have been saved
	# as a Desk home independently of the admin root corrected in v0_0_51.
	users = frappe.get_all("User", filters={"default_workspace": PLAN_WORKSPACE}, pluck="name")
	for user in users:
		roles = set(frappe.get_roles(user))
		if user == "Administrator" or roles & set(PLAN_ROLES):
			continue
		frappe.db.set_value("User", user, "default_workspace", None, update_modified=False)
		frappe.clear_document_cache("User", user)

	frappe.clear_document_cache("Workspace", PLAN_WORKSPACE)
	frappe.cache.delete_key("bootinfo")
