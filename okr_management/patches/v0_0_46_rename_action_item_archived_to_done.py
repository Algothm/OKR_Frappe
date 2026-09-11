import frappe


def execute():
	"""Rename only Action Item lifecycle values; other DocType archive states are untouched."""
	frappe.db.set_value(
		"OKR Action Item",
		{"status": "Archived"},
		"status",
		"Done",
		update_modified=False,
	)
	frappe.db.set_value(
		"OKR Check In",
		{"action_status": "Archived"},
		"action_status",
		"Done",
		update_modified=False,
	)
