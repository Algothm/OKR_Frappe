import frappe

def execute():
	if not frappe.db.has_column("OKR Key Result", "lock_measurement_fields_for_action_item_assignees"):
		return
	frappe.db.sql("""
		UPDATE `tabOKR Key Result`
		SET lock_measurement_fields_for_action_item_assignees = 1
		WHERE lock_measurement_fields_for_action_item_assignees IS NULL
	""")
