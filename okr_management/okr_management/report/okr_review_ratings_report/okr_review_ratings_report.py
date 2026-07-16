from __future__ import annotations

import frappe

from okr_management.insights import get_review_rating_rows


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = []
	for row in get_review_rating_rows(include_normal=True):
		if filters.get("plan") and row.get("plan") != filters.plan:
			continue
		if filters.get("owner") and row.get("owner") != filters.owner:
			continue
		if filters.get("review_status") and row.get("review_status") != filters.review_status:
			continue
		data.append({
			"plan": row.get("plan"),
			"objective": row.get("objective"),
			"objective_title": row.get("objective_title"),
			"owner": row.get("owner"),
			"reviewer": row.get("reviewer"),
			"self_rating": row.get("self_rating"),
			"manager_rating": row.get("manager_rating"),
			"overall_rating": row.get("overall_rating"),
			"rating_gap": row.get("rating_gap"),
			"decision": row.get("decision"),
			"review_status": row.get("review_status"),
			"review_date": row.get("review_date"),
			"manager_feedback": row.get("manager_feedback"),
		})
	return columns, data


def get_columns():
	return [
		{"label": "Plan", "fieldname": "plan", "fieldtype": "Link", "options": "OKR Plan", "width": 170},
		{"label": "Objective", "fieldname": "objective", "fieldtype": "Link", "options": "OKR Objective", "width": 180},
		{"label": "Objective Title", "fieldname": "objective_title", "fieldtype": "Data", "width": 260},
		{"label": "Owner", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Reviewer", "fieldname": "reviewer", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Self Rating", "fieldname": "self_rating", "fieldtype": "Float", "width": 105},
		{"label": "Manager Rating", "fieldname": "manager_rating", "fieldtype": "Float", "width": 120},
		{"label": "Overall Rating", "fieldname": "overall_rating", "fieldtype": "Float", "width": 120},
		{"label": "Rating Gap", "fieldname": "rating_gap", "fieldtype": "Float", "width": 105},
		{"label": "Decision", "fieldname": "decision", "fieldtype": "Data", "width": 150},
		{"label": "Review Status", "fieldname": "review_status", "fieldtype": "Data", "width": 120},
		{"label": "Review Date", "fieldname": "review_date", "fieldtype": "Date", "width": 120},
		{"label": "Manager Feedback", "fieldname": "manager_feedback", "fieldtype": "Small Text", "width": 300},
	]
