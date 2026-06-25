from __future__ import annotations

import frappe
from frappe.utils import date_diff, getdate, nowdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    conditions = []
    values = {}
    if filters.get("cycle"):
        conditions.append("ai.cycle = %(cycle)s")
        values["cycle"] = filters.cycle
    if filters.get("objective"):
        conditions.append("ai.objective = %(objective)s")
        values["objective"] = filters.objective
    if filters.get("key_result"):
        conditions.append("ai.key_result = %(key_result)s")
        values["key_result"] = filters.key_result
    if filters.get("owner"):
        conditions.append("ai.owner_user = %(owner)s")
        values["owner"] = filters.owner
    if filters.get("status"):
        conditions.append("ai.status = %(status)s")
        values["status"] = filters.status
    if filters.get("priority"):
        conditions.append("ai.priority = %(priority)s")
        values["priority"] = filters.priority
    where = " where " + " and ".join(conditions) if conditions else ""
    rows = frappe.db.sql(
        f"""
        select
            ai.cycle,
            ai.objective,
            obj.objective_title,
            ai.key_result,
            kr.key_result_title,
            ai.name as action_item,
            ai.action_item_title,
            ai.owner_user as owner,
            ai.department,
            ai.status,
            ai.priority,
            ai.start_date,
            ai.due_date,
            ai.blockers
        from `tabOKR Action Item` ai
        left join `tabOKR Objective` obj on obj.name = ai.objective
        left join `tabOKR Key Result` kr on kr.name = ai.key_result
        {where}
        order by ai.due_date asc, ai.priority desc, ai.modified desc
        """,
        values,
        as_dict=True,
    )
    today = getdate(nowdate())
    for row in rows:
        row["days_remaining"] = date_diff(getdate(row.due_date), today) if row.get("due_date") else None
    return columns, rows


def get_columns():
    return [
        {"label": "Cycle", "fieldname": "cycle", "fieldtype": "Link", "options": "OKR Cycle", "width": 160},
        {"label": "Objective", "fieldname": "objective", "fieldtype": "Link", "options": "OKR Objective", "width": 170},
        {"label": "Objective Title", "fieldname": "objective_title", "fieldtype": "Data", "width": 220},
        {"label": "Key Result", "fieldname": "key_result", "fieldtype": "Link", "options": "OKR Key Result", "width": 170},
        {"label": "Key Result Title", "fieldname": "key_result_title", "fieldtype": "Data", "width": 240},
        {"label": "Action Item", "fieldname": "action_item", "fieldtype": "Link", "options": "OKR Action Item", "width": 170},
        {"label": "Action Item Title", "fieldname": "action_item_title", "fieldtype": "Data", "width": 240},
        {"label": "Owner", "fieldname": "owner", "fieldtype": "Link", "options": "User", "width": 180},
        {"label": "Department", "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 170},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": "Priority", "fieldname": "priority", "fieldtype": "Data", "width": 100},
        {"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 110},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 110},
        {"label": "Days Remaining", "fieldname": "days_remaining", "fieldtype": "Int", "width": 120},
        {"label": "Blockers", "fieldname": "blockers", "fieldtype": "Small Text", "width": 280},
    ]
