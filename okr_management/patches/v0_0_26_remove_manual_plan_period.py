import frappe


def execute():
    frappe.db.delete("Custom Field", {"dt": "OKR Plan", "fieldname": ["in", [
        "period_selection", "custom_start_date", "custom_end_date",
        "sprint_timeline_preview", "sprint_end_date_preview", "custom_timeline_preview",
    ]]})
