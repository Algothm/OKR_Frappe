from __future__ import annotations

import frappe


def before_install() -> None:
	pass


def after_install() -> None:
	create_roles()


def create_roles() -> None:
	roles = [
		"OKR Admin",
		"OKR Manager",
		"Department Head",
		"Team Lead",
		"Employee",
		"Reviewer",
		"Executive Viewer",
		"HRBP",
	]
	for role in roles:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
