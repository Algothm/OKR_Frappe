from __future__ import annotations

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": "Owner", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 190},
		{"label": "Objective Count", "fieldname": "objective_count", "fieldtype": "Int", "width": 130},
		{"label": "Key Result Count", "fieldname": "key_result_count", "fieldtype": "Int", "width": 140},
		{"label": "Average Objective Progress", "fieldname": "avg_objective_progress", "fieldtype": "Percent", "width": 190},
		{"label": "Average KR Progress", "fieldname": "avg_kr_progress", "fieldtype": "Percent", "width": 160},
		{"label": "Average Confidence", "fieldname": "avg_confidence", "fieldtype": "Float", "width": 150},
		{"label": "Check-in Count", "fieldname": "checkin_count", "fieldtype": "Int", "width": 130},
		{"label": "Last Check-in", "fieldname": "last_checkin", "fieldtype": "Date", "width": 120},
	]
	base_filters = {"plan": filters.plan} if filters.get("plan") else {}
	owners = set(frappe.get_all("OKR Objective", filters=base_filters, pluck="owner_user")) | set(frappe.get_all("OKR Key Result", filters=base_filters, pluck="assignee")) | set(frappe.get_all("OKR Check In", filters=base_filters, pluck="reported_by"))
	if filters.get("owner"):
		owners = {filters.owner}
	data = []
	for owner in sorted(filter(None, owners)):
		objective_filters = {**base_filters, "owner_user": owner}
		kr_filters = {**base_filters, "assignee": owner}
		checkin_filters = {**base_filters, "reported_by": owner}
		obj = frappe.get_all("OKR Objective", filters=objective_filters, fields=["progress", "confidence"])
		krs = frappe.get_all("OKR Key Result", filters=kr_filters, fields=["target_progress", "confidence"])
		checkins = frappe.get_all("OKR Check In", filters=checkin_filters, fields=["checkin_date"], order_by="checkin_date desc")
		obj_avg = sum(flt(x.progress) for x in obj) / len(obj) if obj else 0
		kr_avg = sum(flt(x.target_progress) for x in krs) / len(krs) if krs else 0
		conf_values = [flt(x.confidence) for x in obj + krs if x.confidence]
		data.append({"owner": owner, "objective_count": len(obj), "key_result_count": len(krs), "avg_objective_progress": obj_avg, "avg_kr_progress": kr_avg, "avg_confidence": (sum(conf_values) / len(conf_values) if conf_values else 0), "checkin_count": len(checkins), "last_checkin": checkins[0].checkin_date if checkins else None})
	return columns, data
