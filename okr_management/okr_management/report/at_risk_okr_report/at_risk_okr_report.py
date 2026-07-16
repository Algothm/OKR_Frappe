from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, getdate, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": "Type", "fieldname": "type", "fieldtype": "Data", "width": 110},
		{"label": "Record", "fieldname": "record", "fieldtype": "Dynamic Link", "options": "type", "width": 180},
		{"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 260},
		{"label": "Plan", "fieldname": "plan", "fieldtype": "Link", "options": "OKR Plan", "width": 160},
		{"label": "Owner", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Progress", "fieldname": "progress", "fieldtype": "Percent", "width": 100},
		{"label": "Confidence", "fieldname": "confidence", "fieldtype": "Float", "width": 100},
		{"label": "End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 110},
		{"label": "Reason", "fieldname": "reason", "fieldtype": "Small Text", "width": 260},
	]
	near_end = getdate(add_days(nowdate(), int(filters.get("days_to_end") or 14)))
	data, obj_filters, kr_filters = [], {}, {}
	if filters.get("plan"):
		obj_filters["plan"] = filters.plan; kr_filters["parent_plan"] = filters.plan
	if filters.get("owner"):
		obj_filters["owner_user"] = filters.owner; kr_filters["owner_user"] = filters.owner
	for row in frappe.get_all("OKR Objective", filters=obj_filters, fields=["name", "objective_title", "plan", "owner_user", "status", "progress", "confidence", "end_date"]):
		reasons = []
		if row.status == "At Risk": reasons.append("Marked At Risk")
		if flt(row.progress) < 60 and row.status not in {"Completed", "Cancelled", "Archived"}: reasons.append("Progress below 60%")
		if flt(row.confidence) < 3: reasons.append("Confidence below 3")
		if row.end_date and getdate(row.end_date) <= near_end and flt(row.progress) < 90: reasons.append("End date near")
		if reasons:
			data.append({"type":"OKR Objective","record":row.name,"title":row.objective_title,"plan":row.plan,"owner":row.owner_user,"status":row.status,"progress":row.progress,"confidence":row.confidence,"end_date":row.end_date,"reason":"; ".join(reasons)})
	for row in frappe.get_all("OKR Key Result", filters=kr_filters, fields=["name", "key_result_title", "parent_plan", "owner_user", "status", "target_progress", "end_date"]):
		reasons = []
		if row.status == "At Risk": reasons.append("Marked At Risk")
		if flt(row.target_progress) < 60 and row.status not in {"Achieved", "Closed"}: reasons.append("Progress below 60%")
		if row.end_date and getdate(row.end_date) <= near_end and flt(row.target_progress) < 90: reasons.append("End date near")
		if reasons:
			data.append({"type":"OKR Key Result","record":row.name,"title":row.key_result_title,"plan":row.parent_plan,"owner":row.owner_user,"status":row.status,"progress":row.target_progress,"confidence":None,"end_date":row.end_date,"reason":"; ".join(reasons)})
	return columns, data
