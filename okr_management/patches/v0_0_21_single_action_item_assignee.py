import frappe


CHILD_DOCTYPE = "OKR Action Item Assignee"


def execute():
	if not frappe.db.has_column("OKR Action Item", "assigned_to"):
		return

	if frappe.db.table_exists(CHILD_DOCTYPE):
		rows = frappe.db.sql(
			"""
			select parent, employee
			from `tabOKR Action Item Assignee`
			where parenttype = 'OKR Action Item'
			  and parentfield = 'assignees'
			  and coalesce(employee, '') != ''
			order by parent, idx
			""",
			as_dict=True,
		)
		seen = set()
		for row in rows:
			if row.parent in seen:
				continue
			seen.add(row.parent)
			values = {"assigned_to": row.employee}
			user_id = frappe.db.get_value("Employee", row.employee, "user_id")
			if user_id:
				values["owner_user"] = user_id
			frappe.db.set_value("OKR Action Item", row.parent, values, update_modified=False)

	if frappe.db.exists("DocType", CHILD_DOCTYPE):
		frappe.delete_doc("DocType", CHILD_DOCTYPE, force=True, ignore_permissions=True)
