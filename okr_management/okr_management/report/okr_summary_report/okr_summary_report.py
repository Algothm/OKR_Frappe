from __future__ import annotations

import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"label": "Cycle", "fieldname": "cycle", "fieldtype": "Link", "options": "OKR Cycle", "width": 160},
		{"label": "Objective", "fieldname": "objective", "fieldtype": "Link", "options": "OKR Objective", "width": 180},
		{"label": "Objective Title", "fieldname": "objective_title", "fieldtype": "Data", "width": 220},
		{"label": "Key Result", "fieldname": "key_result", "fieldtype": "Link", "options": "OKR Key Result", "width": 180},
		{"label": "Key Result Title", "fieldname": "key_result_title", "fieldtype": "Data", "width": 240},
		{"label": "Owner", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 180},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": "Progress", "fieldname": "progress", "fieldtype": "Percent", "width": 100},
		{"label": "Confidence", "fieldname": "confidence", "fieldtype": "Float", "width": 100},
		{"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 110},
		{"label": "End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 110},
	]
	conditions, values = [], {}
	if filters.get("cycle"):
		conditions.append("obj.cycle = %(cycle)s")
		values["cycle"] = filters.cycle
	if filters.get("owner"):
		conditions.append("coalesce(kr.owner_user, obj.owner_user) = %(owner)s")
		values["owner"] = filters.owner
	if filters.get("status"):
		conditions.append("coalesce(kr.status, obj.status) = %(status)s")
		values["status"] = filters.status
	where = " where " + " and ".join(conditions) if conditions else ""
	data = frappe.db.sql(f"""
		select obj.cycle, obj.name as objective, obj.objective_title, kr.name as key_result,
			kr.key_result_title, coalesce(kr.owner_user, obj.owner_user) as owner,
			coalesce(kr.status, obj.status) as status, coalesce(kr.target_progress, obj.progress) as progress,
			coalesce(kr.confidence, obj.confidence) as confidence,
			coalesce(kr.start_date, obj.start_date) as start_date, coalesce(kr.end_date, obj.end_date) as end_date
		from `tabOKR Objective` obj
		left join `tabOKR Key Result` kr on kr.objective = obj.name
		{where}
		order by obj.cycle, obj.name, kr.name
		""", values, as_dict=True)
	return columns, data
