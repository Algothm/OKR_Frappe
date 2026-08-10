from __future__ import annotations

import frappe


def execute() -> None:
	for role in ("CEO", "Department Head", "Manager", "Employee"):
		if not frappe.db.exists("Role", role):
			doc = frappe.new_doc("Role")
			doc.role_name = role
			doc.desk_access = 1
			doc.insert(ignore_permissions=True)
