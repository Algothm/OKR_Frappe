from __future__ import annotations

import frappe
from frappe.utils import flt, getdate, nowdate, today

from okr_management.okr_management.page.check_in.check_in import save_quick_checkin


@frappe.whitelist()
def get_workspace_data(year: str | None = None, quarter: str | None = None, sprint: str | None = None, level: str | None = None, owner: str | None = "me") -> dict:
    filters = {}
    if year:
        filters["financial_year"] = year
    if sprint:
        filters["sprint"] = sprint
    if level:
        filters["level"] = level
    if owner == "me":
        filters["owner_user"] = frappe.session.user

    if quarter and not sprint:
        sprint_names = frappe.get_all("OKR Sprint", filters={"financial_quarter": quarter}, pluck="name")
        if not sprint_names:
            return base_response([], year, quarter, sprint, level, owner)
        filters["sprint"] = ["in", sprint_names]

    objectives = frappe.get_all(
        "OKR Objective",
        filters=filters,
        fields=["name", "objective_title", "sprint", "parent_plan", "level", "priority", "owner_user", "status", "progress", "start_date", "end_date"],
        order_by="priority desc, modified desc",
        limit_page_length=100,
    )

    if owner == "me":
        objectives = include_objectives_with_my_action_items(objectives, filters)

    objective_names = [row.name for row in objectives]
    key_results = get_key_results(objective_names)
    action_items = get_action_items([row.name for row in key_results])
    histories = get_checkin_history([row.name for row in action_items])

    actions_by_kr = {}
    for action in action_items:
        action["history"] = histories.get(action.name, [])
        action["has_today_checkin"] = any(str(item.get("checkin_date")) == nowdate() for item in action["history"])
        actions_by_kr.setdefault(action.parent_key_result, []).append(action)

    krs_by_objective = {}
    for kr in key_results:
        kr["action_items"] = actions_by_kr.get(kr.name, [])
        kr["completed_action_items"] = sum(1 for item in kr["action_items"] if item.status in ("Completed", "Closed") or flt(item.progress or 0) >= 100)
        kr["total_action_items"] = len(kr["action_items"])
        kr["total_checkins"] = sum(len(item["history"]) for item in kr["action_items"])
        krs_by_objective.setdefault(kr.objective, []).append(kr)

    hierarchy = []
    for objective in objectives:
        objective["key_results"] = krs_by_objective.get(objective.name, [])
        if owner == "me":
            objective["key_results"] = [kr for kr in objective["key_results"] if kr["action_items"] or kr.owner_user == frappe.session.user]
        if owner != "me" or objective["key_results"] or objective.owner_user == frappe.session.user:
            hierarchy.append(objective)

    return base_response(hierarchy, year, quarter, sprint, level, owner)


@frappe.whitelist()
def get_filter_options() -> dict:
    years = frappe.get_all("Fiscal Year", fields=["name"], order_by="year_start_date desc", limit_page_length=80)
    years = sorted(years, key=lambda row: (0 if row.name == "2026-2027" else 1 if not row.name.startswith("_Test") else 2, row.name), reverse=False)
    return {
        "years": years[:30],
        "sprints": frappe.get_all("OKR Sprint", fields=["name", "sprint_name", "financial_quarter", "financial_year", "status"], order_by="start_date desc", limit_page_length=100),
        "quarters": ["Q1", "Q2", "Q3", "Q4"],
        "levels": ["Organization", "Department", "Team", "Individual"],
    }


@frappe.whitelist()
def save_workspace_checkin(action_item: str, progress: float, update: str, blocker: str | None = None, dependency: str | None = None, attachment: str | None = None, status: str | None = None) -> dict:
    result = save_quick_checkin(action_item, progress, update, blocker, dependency, attachment, status)

    action = frappe.get_doc("OKR Action Item", action_item)
    key_result = frappe.db.get_value(
        "OKR Key Result",
        action.parent_key_result,
        ["name", "key_result_title", "objective", "target_progress", "target_value", "action_item_count", "checkin_count"],
        as_dict=True,
    )
    objective = None
    if key_result and key_result.objective:
        objective = frappe.db.get_value(
            "OKR Objective",
            key_result.objective,
            ["name", "objective_title", "progress"],
            as_dict=True,
        )

    history = get_checkin_history([action_item]).get(action_item, [])
    return {
        "name": result.get("name"),
        "message": result.get("message"),
        "checkin": history[0] if history else None,
        "action_item": {
            "name": action.name,
            "action_item_title": action.action_item_title,
            "parent_key_result": action.parent_key_result,
            "owner_user": action.owner_user,
            "status": action.status,
            "priority": action.priority,
            "progress": flt(action.progress),
            "due_date": action.due_date,
            "history": history,
            "has_today_checkin": any(str(item.get("checkin_date")) == nowdate() for item in history),
        },
        "key_result": key_result,
        "objective": objective,
    }


def base_response(objectives, year, quarter, sprint, level, owner) -> dict:
    return {
        "today": today(),
        "filters": {"year": year, "quarter": quarter, "sprint": sprint, "level": level, "owner": owner or "me"},
        "objectives": objectives,
    }


def include_objectives_with_my_action_items(objectives, filters) -> list:
    names = {row.name for row in objectives}
    action_filters = {"owner_user": frappe.session.user, "status": ["!=", "Cancelled"]}
    actions = frappe.get_all("OKR Action Item", filters=action_filters, fields=["parent_objective"])
    extra_names = {row.parent_objective for row in actions if row.parent_objective and row.parent_objective not in names}
    if not extra_names:
        return objectives
    extra_filters = {"name": ["in", list(extra_names)]}
    if filters.get("financial_year"):
        extra_filters["financial_year"] = filters["financial_year"]
    if filters.get("sprint"):
        extra_filters["sprint"] = filters["sprint"]
    if filters.get("level"):
        extra_filters["level"] = filters["level"]
    extra = frappe.get_all(
        "OKR Objective",
        filters=extra_filters,
        fields=["name", "objective_title", "sprint", "parent_plan", "level", "priority", "owner_user", "status", "progress", "start_date", "end_date"],
        order_by="priority desc, modified desc",
        limit_page_length=100,
    )
    return objectives + extra


def get_key_results(objective_names: list[str]) -> list:
    if not objective_names:
        return []
    return frappe.get_all(
        "OKR Key Result",
        filters={"objective": ["in", objective_names]},
        fields=[
            "name",
            "key_result_title",
            "objective",
            "owner_user",
            "status",
            "priority",
            "target_progress",
            "metric_type",
            "unit_of_measure",
            "target_value",
            "current_value",
            "currency",
            "action_item_count",
            "checkin_count",
        ],
        order_by="priority desc, modified desc",
        limit_page_length=300,
    )


def get_action_items(kr_names: list[str]) -> list:
    if not kr_names:
        return []
    return frappe.get_all(
        "OKR Action Item",
        filters={"parent_key_result": ["in", kr_names], "status": ["!=", "Cancelled"]},
        fields=["name", "action_item_title", "parent_key_result", "owner_user", "status", "priority", "progress", "due_date"],
        order_by="due_date asc, modified desc",
        limit_page_length=800,
    )


def get_checkin_history(action_item_names: list[str]) -> dict:
    if not action_item_names:
        return {}
    rows = frappe.db.sql(
        """
        select row.action_item_id, ci.name, ci.checkin_date, ci.progress, ci.achievements,
               ci.blockers, ci.dependency_description, ci.attachment, ci.reported_by
        from `tabOKR Action Item Row` row
        inner join `tabOKR Check In` ci on ci.name = row.parent
        where row.parenttype = 'OKR Check In'
          and row.action_item_id in %(action_items)s
          and ci.status = 'Submitted'
        order by ci.checkin_date desc, ci.creation desc
        """,
        {"action_items": tuple(action_item_names)},
        as_dict=True,
    )
    out = {}
    for row in rows:
        out.setdefault(row.action_item_id, []).append(row)
    return out
