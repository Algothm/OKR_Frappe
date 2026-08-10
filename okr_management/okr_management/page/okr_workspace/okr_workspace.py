from __future__ import annotations

import frappe
from frappe.utils import flt, getdate, nowdate, today

from okr_management.hierarchy_visibility import get_hierarchy_visibility_scope
from okr_management.utils.periods import add_period_labels


def get_workspace_plan_names() -> list[str]:
    scope = get_hierarchy_visibility_scope()
    filters = {"status": ["in", ["Draft", "Active"]]}
    if scope["read_all"]:
        return frappe.get_all("OKR Plan", filters=filters, pluck="name")

    plan_names = set(scope["full_plan_names"])
    if scope["visible_objectives"]:
        plan_names.update(
            filter(
                None,
                frappe.get_all(
                    "OKR Objective",
                    filters={"name": ["in", list(scope["visible_objectives"])]},
                    pluck="parent_plan",
                ),
            )
        )
    if not plan_names:
        return []
    filters["name"] = ["in", list(plan_names)]
    return frappe.get_all("OKR Plan", filters=filters, pluck="name")


def get_active_plan_names() -> list[str]:
    return frappe.get_all("OKR Plan", filters={"status": "Active"}, pluck="name")


def empty_workspace_response(year, plan, level, owner) -> dict:
    return base_response([], year, plan, level, owner)


@frappe.whitelist()
def get_workspace_data(year: str | None = None, plan: str | None = None, level: str | None = None, owner: str | None = "me") -> dict:
    workspace_plan_names = get_workspace_plan_names()
    if not workspace_plan_names:
        return empty_workspace_response(year, plan, level, owner)

    filters = {"parent_plan": ["in", workspace_plan_names]}
    scope = get_hierarchy_visibility_scope()
    filters["name"] = ["in", list(scope["visible_objectives"])]
    if year:
        filters["financial_year"] = year
    if plan:
        filters["parent_plan"] = plan
    if level:
        filters["level"] = level

    objectives = frappe.get_all(
        "OKR Objective",
        filters=filters,
        fields=["name", "objective_title", "parent_plan", "level", "priority", "owner_user", "status", "progress", "start_date", "end_date"],
        order_by="priority desc, modified desc",
        limit_page_length=100,
    )


    objective_names = [row.name for row in objectives]
    key_results = get_key_results(objective_names)
    key_results = [row for row in key_results if row.name in scope["visible_key_results"]]
    action_items = get_action_items([row.name for row in key_results])
    action_items = [row for row in action_items if row.name in scope["visible_action_items"]]
    add_period_labels(key_results, action_items)
    histories = get_checkin_history([row.name for row in action_items])
    active_plan_names = set(get_active_plan_names())

    actions_by_kr = {}
    for action in action_items:
        action["history"] = histories.get(action.name, [])
        action["has_today_checkin"] = any(str(item.get("checkin_date")) == nowdate() for item in action["history"])
        action["can_checkin"] = action.parent_plan in active_plan_names and (
            scope["checkin_override"] or action.name in scope["direct_action_items"]
        )
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
        if objective["key_results"] or objective.name in scope["owned_objectives"]:
            hierarchy.append(objective)

    return base_response(hierarchy, year, plan, level, owner)


@frappe.whitelist()
def get_filter_options() -> dict:
    workspace_plan_names = get_workspace_plan_names()
    years = frappe.get_all("Fiscal Year", fields=["name"], order_by="year_start_date desc", limit_page_length=80)
    years = sorted(years, key=lambda row: (0 if row.name == "2026-2027" else 1 if not row.name.startswith("_Test") else 2, row.name), reverse=False)
    return {
        "years": years[:30],
        "plans": frappe.get_all(
            "OKR Plan",
            filters={"name": ["in", workspace_plan_names]} if workspace_plan_names else {"name": ["is", "not set"]},
            fields=["name", "plan_name", "financial_year", "status", "planned_activation_date"],
            order_by="modified desc",
            limit_page_length=100,
        ),
        "levels": ["Organization", "Department", "Team", "Individual"],
    }


@frappe.whitelist()
def save_workspace_checkin(action_item: str, progress: float, update: str, blocker: str | None = None, dependency: str | None = None, attachment: str | None = None, status: str | None = None) -> dict:
    scope = get_hierarchy_visibility_scope()
    if not (scope["read_all"] or scope["checkin_override"]) and action_item not in scope["direct_action_items"]:
        frappe.throw("Only the employee assigned to this Action Item can submit its Check-In", frappe.PermissionError)
    doc = frappe.new_doc("OKR Check In")
    doc.action_item = action_item
    doc.progress = flt(progress)
    doc.achievements = update
    doc.blockers = blocker or ""
    doc.dependency = dependency or ""
    doc.attachment = attachment or ""
    doc.action_status = status or "In Progress"
    doc.flags.ignore_permissions = True
    doc.save()
    result = {"name": doc.name, "message": "Check-in saved successfully"}

    action = frappe.get_doc("OKR Action Item", action_item)
    key_result = frappe.db.get_value(
        "OKR Key Result",
        action.parent_key_result,
        ["name", "key_result_title", "objective", "parent_plan", "end_date", "target_progress", "target_value", "action_item_count", "checkin_count"],
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
    add_period_labels([key_result] if key_result else [], [action])
    return {
        "name": result.get("name"),
        "message": result.get("message"),
        "checkin": history[0] if history else None,
        "action_item": {
            "name": action.name,
            "action_item_title": action.action_item_title,
            "parent_key_result": action.parent_key_result,
            "parent_plan": action.parent_plan,
            "period_label": action.get("period_label"),
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


def base_response(objectives, year, plan, level, owner) -> dict:
    return {
        "today": today(),
        "filters": {"year": year, "plan": plan, "level": level, "owner": owner or "me"},
        "objectives": objectives,
    }



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
            "parent_plan",
            "owner_user",
            "assignee",
            "status",
            "priority",
            "target_progress",
            "metric_type",
            "unit_of_measure",
            "target_value",
            "current_value",
            "baseline_value",
            "currency",
            "action_item_count",
            "checkin_count",
            "end_date",
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
        fields=["name", "action_item_title", "parent_key_result", "parent_plan", "owner_user", "status", "priority", "progress", "due_date"],
        order_by="due_date asc, modified desc",
        limit_page_length=800,
    )



def get_checkin_history(action_item_names: list[str]) -> dict:
    if not action_item_names:
        return {}
    rows = frappe.get_all(
        "OKR Check In",
        filters={"action_item": ["in", action_item_names], "status": "Submitted"},
        fields=["action_item", "name", "checkin_date", "progress", "achievements", "blockers", "reported_by"],
        order_by="checkin_date desc, creation desc",
        limit_page_length=2000,
    )
    out = {}
    for row in rows:
        out.setdefault(row.action_item, []).append(row)
    return out
