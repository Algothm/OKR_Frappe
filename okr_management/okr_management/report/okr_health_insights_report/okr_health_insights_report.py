from __future__ import annotations

import frappe
from frappe.utils import cint

from okr_management.insights import get_health_rows, get_review_rating_rows, get_review_rating_signals


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	rating_by_objective = {row.get("objective"): row for row in get_review_rating_signals(include_normal=True)}
	data = []
	for row in get_health_rows():
		if filters.get("plan") and row.get("plan") != filters.plan:
			continue
		if filters.get("department") and row.get("department") != filters.department:
			continue
		if filters.get("owner") and row.get("owner") != filters.owner:
			continue
		if filters.get("risk_level") and row.get("risk_level") != filters.risk_level:
			continue
		if filters.get("type") and row.get("type") != filters.type:
			continue
		if cint(filters.get("only_due_soon")) and not (row.get("days_remaining") is not None and 0 <= row.get("days_remaining") <= 14):
			continue
		if cint(filters.get("only_missed_checkins")) and "Missed check-in" not in (row.get("reasons") or []):
			continue

		doctype = "OKR Objective" if row.get("type") == "Objective" else "OKR Key Result"
		rating = rating_by_objective.get(row.get("record")) if row.get("type") == "Objective" else None
		data.append({
			"doctype": doctype,
			"type": row.get("type"),
			"record": row.get("record"),
			"title": row.get("title"),
			"department": row.get("department"),
			"plan": row.get("plan"),
			"sprint_title": row.get("sprint_title"),
			"owner": row.get("owner"),
			"progress": row.get("progress"),
			"confidence": row.get("confidence"),
			"end_date": row.get("end_date"),
			"days_remaining": row.get("days_remaining"),
			"risk_level": row.get("risk_level"),
			"reason": row.get("reason"),
			"recommended_action": row.get("recommended_action"),
			"self_rating": rating.get("self_rating") if rating else None,
			"manager_rating": rating.get("manager_rating") if rating else None,
			"overall_rating": rating.get("overall_rating") if rating else None,
			"rating_gap": rating.get("rating_gap") if rating else None,
		})
	for rating in get_review_rating_rows(include_normal=True):
		if filters.get("plan") and rating.get("plan") != filters.plan:
			continue
		if filters.get("department") and rating.get("department") != filters.department:
			continue
		if filters.get("owner") and rating.get("owner") != filters.owner:
			continue
		data.append({
			"doctype": "OKR Objective Review",
			"type": "Objective Review",
			"record": rating.get("review"),
			"objective": rating.get("objective"),
			"title": rating.get("objective_title"),
			"department": rating.get("department"),
			"plan": rating.get("plan"),
			"sprint_title": None,
			"owner": rating.get("owner"),
			"progress": None,
			"confidence": None,
			"end_date": None,
			"days_remaining": None,
			"risk_level": rating.get("risk_level"),
			"self_rating": rating.get("self_rating"),
			"manager_rating": rating.get("manager_rating"),
			"overall_rating": rating.get("overall_rating"),
			"rating_gap": rating.get("rating_gap"),
			"review_status": rating.get("review_status"),
			"manager_feedback": rating.get("manager_feedback"),
			"reason": "Review rating visibility",
			"recommended_action": rating.get("recommended_action"),
		})
	return columns, data


def get_columns():
	return [
		{"label": "DocType", "fieldname": "doctype", "fieldtype": "Data", "hidden": 1, "width": 120},
		{"label": "Type", "fieldname": "type", "fieldtype": "Data", "width": 105},
		{"label": "Record", "fieldname": "record", "fieldtype": "Dynamic Link", "options": "doctype", "width": 170},
		{"label": "Objective", "fieldname": "objective", "fieldtype": "Link", "options": "OKR Objective", "width": 170},
		{"label": "Title", "fieldname": "title", "fieldtype": "Data", "width": 260},
		{"label": "Department", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 180},
		{"label": "Plan", "fieldname": "plan", "fieldtype": "Link", "options": "OKR Plan", "width": 160},
		{"label": "Plan Title", "fieldname": "sprint_title", "fieldtype": "Data", "width": 180},
		{"label": "Owner", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 190},
		{"label": "Progress", "fieldname": "progress", "fieldtype": "Percent", "width": 95},
		{"label": "Confidence", "fieldname": "confidence", "fieldtype": "Float", "width": 95},
		{"label": "End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 110},
		{"label": "Days Remaining", "fieldname": "days_remaining", "fieldtype": "Int", "width": 120},
		{"label": "Risk Level", "fieldname": "risk_level", "fieldtype": "Data", "width": 110},
		{"label": "Self Rating", "fieldname": "self_rating", "fieldtype": "Float", "width": 105},
		{"label": "Manager Rating", "fieldname": "manager_rating", "fieldtype": "Float", "width": 120},
		{"label": "Overall Rating", "fieldname": "overall_rating", "fieldtype": "Float", "width": 120},
		{"label": "Rating Gap", "fieldname": "rating_gap", "fieldtype": "Float", "width": 105},
		{"label": "Review Status", "fieldname": "review_status", "fieldtype": "Data", "width": 120},
		{"label": "Manager Feedback", "fieldname": "manager_feedback", "fieldtype": "Small Text", "width": 260},
		{"label": "Reason", "fieldname": "reason", "fieldtype": "Small Text", "width": 300},
		{"label": "Recommended Action", "fieldname": "recommended_action", "fieldtype": "Small Text", "width": 320},
	]
