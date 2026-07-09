from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, today

from okr_management.utils.okr_calculations import recalculate_key_result_progress


@frappe.whitelist()
def get_checkin_page_data(show_all: int = 0, status: str | None = None) -> dict:
    user = frappe.session.user
    filters = {"status": ["!=", "Cancelled"]}
    if not int(show_all or 0):
        filters["owner_user"] = user
    if status:
        filters["status"] = status

    action_items = frappe.get_all(
        "OKR Action Item",
        filters=filters,
        fields=[
            "name",
            "action_item_title",
            "owner_user",
            "status",
            "priority",
            "progress",
            "due_date",
            "parent_key_result",
            "parent_objective",
            "parent_sprint",
            "parent_plan",
            "company",
            "department",
        ],
        order_by="due_date asc, modified desc",
        limit_page_length=100,
    )

    kr_names = [row.parent_key_result for row in action_items if row.parent_key_result]
    kr_map = get_key_result_map(kr_names)
    latest_map = get_latest_checkin_map([row.name for row in action_items])
    today_map = get_today_checkin_map([row.name for row in action_items])

    rows = []
    pending_count = 0
    today_date = getdate(today())
    for row in action_items:
        kr = kr_map.get(row.parent_key_result, {})
        latest = latest_map.get(row.name, {})
        has_today = bool(today_map.get(row.name))
        is_pending = row.status not in {"Completed", "Cancelled"}
        if is_pending:
            pending_count += 1
        overdue = bool(row.due_date and getdate(row.due_date) < today_date and is_pending)

        rows.append(
            {
                "name": row.name,
                "action_item_title": row.action_item_title,
                "key_result": row.parent_key_result,
                "key_result_title": kr.get("key_result_title") or row.parent_key_result,
                "objective": row.parent_objective or kr.get("objective"),
                "objective_title": kr.get("objective_title") or row.parent_objective,
                "parent_plan": row.parent_plan or kr.get("parent_plan"),
                "parent_sprint": row.parent_sprint or kr.get("parent_sprint"),
                "company": row.company or kr.get("company"),
                "department": row.department or kr.get("department"),
                "owner_user": row.owner_user,
                "status": row.status,
                "priority": row.priority,
                "progress": flt(row.progress),
                "due_date": row.due_date,
                "last_checkin": latest.get("checkin_date"),
                "last_checkin_progress": latest.get("progress"),
                "has_today_checkin": has_today,
                "overdue": overdue,
            }
        )

    return {
        "today": today(),
        "pending_count": pending_count,
        "action_items": rows,
        "recent_checkins": get_recent_checkins(user),
    }


@frappe.whitelist()
def save_quick_checkin(action_item: str, progress: float, update: str, blocker: str | None = None, dependency: str | None = None, attachment: str | None = None, status: str | None = None) -> dict:
    if not action_item or not frappe.db.exists("OKR Action Item", action_item):
        frappe.throw(_("Action Item is required."))
    if not update:
        frappe.throw(_("Description / Update is required."))

    action = frappe.get_doc("OKR Action Item", action_item)
    if not action.parent_key_result:
        frappe.throw(_("Action Item is not linked to a Key Result."))

    kr_status = frappe.db.get_value("OKR Key Result", action.parent_key_result, "status")
    if kr_status not in {"Draft", "Active"}:
        frappe.throw(_("Check-ins are only allowed when the Parent Key Result is Draft or Active."))

    progress = min(100.0, max(0.0, flt(progress)))
    
    if status and status in {"Open", "In Progress", "Blocked", "Completed", "Cancelled", "On Hold"}:
        new_status = status
    else:
        new_status = action.status
        if progress >= 100 and action.status != "Cancelled":
            new_status = "Completed"
        elif action.status in {"Open", "Blocked"} and progress > 0:
            new_status = "In Progress"

    if progress >= 100:
        new_status = "Completed"

    doc = frappe.get_doc(
        {
            "doctype": "OKR Check In",
            "key_result": action.parent_key_result,
            "reported_by": frappe.session.user,
            "checkin_date": nowdate(),
            "progress": progress,
            "current_value": progress,
            "achievements": update,
            "blockers": blocker or "",
            "dependency_description": dependency or "",
            "attachment": attachment or "",
            "action_items": [
                {
                    "action_item_id": action.name,
                    "action_item_title": action.action_item_title,
                    "owner_user": action.owner_user,
                    "priority": action.priority,
                    "status": new_status,
                    "progress": progress,
                    "due_date": action.due_date,
                    "notes": update,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    recalculate_key_result_progress(action.parent_key_result)
    frappe.db.commit()
    return {"name": doc.name, "message": _("Check-In saved")}


def get_key_result_map(names: list[str]) -> dict:
    if not names:
        return {}
    rows = frappe.get_all(
        "OKR Key Result",
        filters={"name": ["in", list(set(names))]},
        fields=["name", "key_result_title", "objective", "objective_title", "parent_plan", "parent_sprint", "company", "department"],
        limit_page_length=500,
    )
    return {row.name: row for row in rows}


def get_latest_checkin_map(action_items: list[str]) -> dict:
    if not action_items:
        return {}
    rows = frappe.db.sql(
        """
        select row.action_item_id, ci.name, ci.checkin_date, ci.progress
        from `tabOKR Action Item Row` row
        inner join `tabOKR Check In` ci on ci.name = row.parent
        where row.parenttype = 'OKR Check In'
          and row.action_item_id in %(action_items)s
          and ci.status = 'Submitted'
        order by ci.checkin_date desc, ci.creation desc
        """,
        {"action_items": tuple(action_items)},
        as_dict=True,
    )
    out = {}
    for row in rows:
        out.setdefault(row.action_item_id, row)
    return out


def get_today_checkin_map(action_items: list[str]) -> dict:
    if not action_items:
        return {}
    rows = frappe.db.sql(
        """
        select row.action_item_id, ci.name
        from `tabOKR Action Item Row` row
        inner join `tabOKR Check In` ci on ci.name = row.parent
        where row.parenttype = 'OKR Check In'
          and row.action_item_id in %(action_items)s
          and ci.status = 'Submitted'
          and ci.checkin_date = %(today)s
        """,
        {"action_items": tuple(action_items), "today": nowdate()},
        as_dict=True,
    )
    return {row.action_item_id: row.name for row in rows}


def get_recent_checkins(user: str) -> list[dict]:
    rows = frappe.get_all(
        "OKR Check In",
        filters={"reported_by": user, "status": "Submitted"},
        fields=["name", "key_result", "checkin_date", "progress", "achievements", "creation"],
        order_by="checkin_date desc, creation desc",
        limit_page_length=10,
    )
    kr_map = get_key_result_map([row.key_result for row in rows if row.key_result])
    return [
        {
            "name": row.name,
            "key_result": row.key_result,
            "key_result_title": kr_map.get(row.key_result, {}).get("key_result_title") or row.key_result,
            "checkin_date": row.checkin_date,
            "progress": flt(row.progress),
            "update": row.achievements,
        }
        for row in rows
    ]
