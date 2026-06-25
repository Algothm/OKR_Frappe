from __future__ import annotations

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": "Cycle", "fieldname": "cycle", "fieldtype": "Link", "options": "OKR Cycle", "width": 170},
		{"label": "Cycle Name", "fieldname": "cycle_name", "fieldtype": "Data", "width": 220},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": "Objective Count", "fieldname": "objective_count", "fieldtype": "Int", "width": 130},
		{"label": "Key Result Count", "fieldname": "key_result_count", "fieldtype": "Int", "width": 140},
		{"label": "Average Progress", "fieldname": "average_progress", "fieldtype": "Percent", "width": 140},
		{"label": "Pending Reviews", "fieldname": "pending_reviews", "fieldtype": "Int", "width": 130},
		{"label": "Approved Reviews", "fieldname": "approved_reviews", "fieldtype": "Int", "width": 130},
		{"label": "Review Status", "fieldname": "review_status", "fieldtype": "Data", "width": 160},
	]
	cycle_filters = {}
	if filters.get("cycle"):
		cycle_filters["name"] = filters.cycle
	if filters.get("status"):
		cycle_filters["status"] = filters.status
	data = []
	for cycle in frappe.get_all("OKR Cycle", filters=cycle_filters, fields=["name", "cycle_name", "status"], order_by="start_date desc"):
		objectives = frappe.get_all("OKR Objective", filters={"cycle": cycle.name}, fields=["name", "progress"])
		krs = frappe.db.count("OKR Key Result", {"cycle": cycle.name})
		pending = frappe.db.count("OKR Objective Review", {"cycle": cycle.name, "review_status": ["in", ["Draft", "Submitted"]]})
		approved = frappe.db.count("OKR Objective Review", {"cycle": cycle.name, "review_status": "Approved"})
		avg = sum(flt(row.progress) for row in objectives) / len(objectives) if objectives else 0
		review_status = "Pending" if pending else ("Reviewed" if approved else "Not Started")
		data.append({"cycle": cycle.name, "cycle_name": cycle.cycle_name, "status": cycle.status, "objective_count": len(objectives), "key_result_count": krs, "average_progress": avg, "pending_reviews": pending, "approved_reviews": approved, "review_status": review_status})
	return columns, data
