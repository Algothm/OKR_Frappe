# Copyright (c) 2026, Ajanta Bottles and contributors
# For license information, please see license.txt

from __future__ import annotations

from collections import Counter, defaultdict

import frappe
from frappe.utils import add_days, flt, getdate, today

from okr_management.okr_management.doctype.okr_plan.okr_plan import get_period_label


no_cache = 1
def require_admin_workspace_access() -> None:
    if frappe.session.user == "Administrator":
        return
    frappe.throw("You are not permitted to access the Admin Workspace.", frappe.PermissionError)


def get_context(context):
    context.no_cache = 1


@frappe.whitelist()
def get_filter_options() -> dict:
    require_admin_workspace_access()
    years = frappe.get_all("Fiscal Year", fields=["name"], order_by="year_start_date desc", limit_page_length=50)
    plans = frappe.get_all(
        "OKR Plan",
        fields=["name", "plan_name", "financial_year", "sprint_frequency", "status"],
        order_by="modified desc",
        limit_page_length=500,
    )
    departments = frappe.get_all(
        "Department", fields=["name", "department_name"], order_by="department_name asc", limit_page_length=500
    )
    return {
        "years": years,
        "sprints": plans, "plans": plans, "departments": departments,
        "owners": get_owner_options(),
        "statuses": ["Draft", "Active", "On Hold", "Completed", "Closed", "Archived"],
    }


@frappe.whitelist()
def get_dashboard_data(year=None, quarter=None, plan=None, sprint=None, department=None, owner=None, status=None) -> dict:
    require_admin_workspace_access()
    filters = scrub_filters(year, quarter, plan or sprint, department, owner, status)
    plan_names = get_plan_names(filters)
    all_objectives = get_objectives(filters, plan_names)
    achieved_objectives = [
        row for row in all_objectives
        if flt(row.progress) >= 100 or row.status in {"Completed", "Closed"}
    ]
    objectives = [row for row in all_objectives if row not in achieved_objectives]
    objective_names = [row.name for row in objectives]
    key_results = get_key_results(filters, plan_names, objective_names)
    kr_names = [row.name for row in key_results]
    action_items = get_action_items(filters, plan_names, objective_names, kr_names)
    add_period_labels(key_results, action_items)
    checkins = get_checkins(filters, plan_names, objective_names, kr_names)
    plans = get_plans(filters, plan_names)
    department_performance = build_department_performance(objectives, key_results, action_items)
    metrics = build_metrics(objectives, action_items)
    metrics["departments_at_risk"] = len([row for row in department_performance if row["status"] in {"At Risk", "Critical"}])
    attention_list, attention_count = build_attention_required(objectives, action_items, checkins)
    metrics["achieved_objectives"] = len(achieved_objectives)
    return {
        "filters": filters, "metrics": metrics,
        "department_performance": department_performance,
        "department_comparison": build_department_comparison(department_performance),
        "attention_required": attention_list,
        "achieved_objectives": achieved_objectives,
        "attention_count": attention_count,
        "critical_activity": build_critical_activity(objectives, action_items, plans),
        "manager_performance": build_manager_performance(objectives, action_items),
        "plan_summaries": build_plan_summaries(plans, objectives, key_results, action_items, checkins, []),
        "updated_at": frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
    }


def scrub_filters(year, quarter, plan, department, owner, status) -> dict:
    return {"year": year or "", "quarter": quarter or "", "plan": plan or "",
            "department": department or "", "owner": owner or "", "status": status or ""}


def get_owner_options() -> list[dict]:
    owners = set()
    for doctype, fieldname in (("OKR Objective", "owner_user"), ("OKR Key Result", "owner_user"),
                               ("OKR Action Item", "owner_user"), ("OKR Check In", "reported_by")):
        rows = frappe.get_all(doctype, fields=[fieldname], limit_page_length=1000)
        owners.update(row.get(fieldname) for row in rows if row.get(fieldname))
    if not owners:
        return []
    return frappe.get_all("User", filters={"name": ["in", list(owners)]},
                          fields=["name", "full_name"], order_by="full_name asc", limit_page_length=1000)


def get_plan_names(filters: dict) -> list[str] | None:
    plan_filters = {}
    if filters.get("plan"):
        plan_filters["name"] = filters["plan"]
    if filters.get("year"):
        plan_filters["financial_year"] = filters["year"]
    if filters.get("owner"):
        plan_filters["owner_user"] = filters["owner"]
    if filters.get("department"):
        names = frappe.get_all("OKR Objective", filters={"department": filters["department"]}, pluck="parent_plan")
        plan_filters["name"] = ["in", names or ["__none__"]]
    if not plan_filters:
        return None
    return frappe.get_all("OKR Plan", filters=plan_filters, pluck="name", limit_page_length=1000)


def add_common_filters(out: dict, filters: dict, owner_field: str = "owner_user") -> None:
    if filters.get("year"):
        out["financial_year"] = filters["year"]
    if filters.get("department"):
        out["department"] = filters["department"]
    if filters.get("owner"):
        out[owner_field] = filters["owner"]
    if filters.get("status"):
        out["status"] = filters["status"]


def apply_names_filter(out: dict, fieldname: str, names: list[str] | None) -> None:
    if names is not None:
        out[fieldname] = ["in", names or ["__none__"]]


def get_plans(filters: dict, plan_names: list[str] | None) -> list[dict]:
    doc_filters = {}
    if filters.get("year"):
        doc_filters["financial_year"] = filters["year"]
    if filters.get("owner"):
        doc_filters["owner_user"] = filters["owner"]
    apply_names_filter(doc_filters, "name", plan_names)
    return frappe.get_all(
        "OKR Plan", filters=doc_filters,
        fields=["name", "plan_name", "financial_year", "sprint_frequency",
                "owner_user", "status", "progress", "modified", "creation"], limit_page_length=5000,
    )


def get_objectives(filters: dict, plan_names: list[str] | None) -> list[dict]:
    doc_filters = {}
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    return frappe.get_all(
        "OKR Objective", filters=doc_filters,
        fields=["name", "objective_title", "parent_plan", "financial_year", "department",
                "owner_user", "status", "priority", "progress", "confidence", "end_date",
                "modified", "creation"], order_by="progress asc, modified desc", limit_page_length=10000,
    )


def get_key_results(filters: dict, plan_names: list[str] | None, objective_names: list[str]) -> list[dict]:
    doc_filters = {}
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    if objective_names:
        doc_filters["objective"] = ["in", objective_names]
    elif plan_names is not None:
        doc_filters["objective"] = ["in", ["__none__"]]
    return frappe.get_all(
        "OKR Key Result", filters=doc_filters,
        fields=["name", "key_result_title", "objective", "parent_plan", "financial_year", "department",
                "owner_user", "status", "target_progress", "end_date", "modified", "creation"], limit_page_length=20000,
    )


def get_action_items(filters: dict, plan_names: list[str] | None, objective_names: list[str], kr_names: list[str]) -> list[dict]:
    doc_filters = {"status": ["!=", "Cancelled"]}
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    if objective_names:
        doc_filters["parent_objective"] = ["in", objective_names]
    if kr_names:
        doc_filters["parent_key_result"] = ["in", kr_names]
    elif plan_names is not None:
        doc_filters["parent_key_result"] = ["in", ["__none__"]]
    return frappe.get_all(
        "OKR Action Item", filters=doc_filters,
        fields=["name", "action_item_title", "parent_key_result", "parent_objective", "parent_plan",
                "financial_year", "department", "owner_user", "status", "priority", "progress",
                "due_date", "modified", "creation"], order_by="due_date asc, modified desc",
        limit_page_length=20000,
    )


def add_period_labels(key_results: list, action_items: list) -> None:
    plan_names = {row.parent_plan for row in [*key_results, *action_items] if row.get("parent_plan")}
    plans = {
        row.name: row
        for row in frappe.get_all(
            "OKR Plan",
            filters={"name": ["in", list(plan_names)]},
            fields=["name", "financial_year", "sprint_frequency"],
        )
    } if plan_names else {}
    for row, date_field in ([(row, "end_date") for row in key_results] + [(row, "due_date") for row in action_items]):
        plan = plans.get(row.get("parent_plan"))
        row["period_label"] = get_period_label(row.get(date_field), plan) if plan else ""


def get_checkins(filters: dict, plan_names: list[str] | None, objective_names: list[str], kr_names: list[str]) -> list[dict]:
    doc_filters = {"status": "Submitted"}
    if filters.get("year"):
        doc_filters["financial_year"] = filters["year"]
    if filters.get("department"):
        doc_filters["department"] = filters["department"]
    if filters.get("owner"):
        doc_filters["reported_by"] = filters["owner"]
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    if objective_names:
        doc_filters["objective"] = ["in", objective_names]
    if kr_names:
        doc_filters["key_result"] = ["in", kr_names]
    elif plan_names is not None:
        doc_filters["key_result"] = ["in", ["__none__"]]
    return frappe.get_all(
        "OKR Check In", filters=doc_filters,
        fields=["name", "checkin_date", "reported_by", "key_result", "objective", "parent_plan",
                "department", "progress", "confidence", "blockers", "modified", "creation"],
        order_by="checkin_date desc, creation desc", limit_page_length=20000,
    )


def build_plan_summaries(plans, objectives, key_results, action_items, checkins, sprints) -> list[dict]:
    recent_cutoff = getdate(add_days(today(), -7))

    objectives_by_plan = defaultdict(list)
    key_results_by_plan = Counter()
    blocked_objectives_by_plan = defaultdict(set)
    overdue_actions_by_plan = Counter()
    recent_checkins_by_plan = defaultdict(set)
    checkin_dates_by_plan = defaultdict(list)
    departments_by_plan = defaultdict(set)
    target_dates_by_plan = defaultdict(list)
    modified_by_plan = defaultdict(list)

    for row in sprints:
        if row.parent_plan and row.end_date:
            target_dates_by_plan[row.parent_plan].append(row.end_date)
        if row.parent_plan and row.modified:
            modified_by_plan[row.parent_plan].append(row.modified)

    for row in objectives:
        if not row.parent_plan:
            continue
        objectives_by_plan[row.parent_plan].append(row)
        if row.department:
            departments_by_plan[row.parent_plan].add(row.department)
        if row.status == "Blocked":
            blocked_objectives_by_plan[row.parent_plan].add(row.name)
        if row.modified:
            modified_by_plan[row.parent_plan].append(row.modified)

    for row in key_results:
        if row.parent_plan:
            key_results_by_plan[row.parent_plan] += 1
            if row.department:
                departments_by_plan[row.parent_plan].add(row.department)
            if row.modified:
                modified_by_plan[row.parent_plan].append(row.modified)

    for row in action_items:
        if not row.parent_plan:
            continue
        if row.status == "Blocked" and row.parent_objective:
            blocked_objectives_by_plan[row.parent_plan].add(row.parent_objective)
        if is_overdue(row):
            overdue_actions_by_plan[row.parent_plan] += 1
        if row.department:
            departments_by_plan[row.parent_plan].add(row.department)
        if row.modified:
            modified_by_plan[row.parent_plan].append(row.modified)

    for row in checkins:
        if row.parent_plan and row.objective and row.checkin_date and getdate(row.checkin_date) >= recent_cutoff:
            recent_checkins_by_plan[row.parent_plan].add(row.objective)
        if row.parent_plan and row.checkin_date:
            checkin_dates_by_plan[row.parent_plan].append(row.checkin_date)
        if row.parent_plan and row.modified:
            modified_by_plan[row.parent_plan].append(row.modified)

    rows = []
    for plan in plans:
        plan_objectives = objectives_by_plan.get(plan.name, [])
        active_objectives = [row for row in plan_objectives if is_active_objective(row)]
        progress = average([row.progress for row in plan_objectives])
        blocked_objectives = len(blocked_objectives_by_plan.get(plan.name, set()))
        overdue_actions = overdue_actions_by_plan.get(plan.name, 0)
        stale_checkins = len([row for row in active_objectives if row.name not in recent_checkins_by_plan.get(plan.name, set())])
        last_updates = modified_by_plan.get(plan.name, []) + [plan.modified or plan.creation]
        target_dates = target_dates_by_plan.get(plan.name, [])
        rows.append({
            "name": plan.name,
            "plan_name": plan.plan_name or plan.name,
            "financial_year": plan.financial_year or "",
            "sprint_frequency": plan.sprint_frequency or "",
            "status": plan.status or "",
            "progress": progress,
            "objectives": len(plan_objectives),
            "key_results": key_results_by_plan.get(plan.name, 0),
            "departments": len(departments_by_plan.get(plan.name, set())),
            "blocked": blocked_objectives,
            "blocked_objectives": blocked_objectives,
            "overdue_action_items": overdue_actions,
            "stale_checkins": stale_checkins,
            "health": plan_health(progress, blocked_objectives, overdue_actions, stale_checkins),
            "target_date": str(max(target_dates)) if target_dates else "",
            "last_checkin": str(max(checkin_dates_by_plan.get(plan.name, []), default="")),
            "last_updated": str(max([value for value in last_updates if value], default=plan.modified or plan.creation or "")),
        })
    return rows


def plan_health(progress: float, blocked_objectives: int, overdue_actions: int, stale_checkins: int) -> str:
    if blocked_objectives > 0 or overdue_actions >= 3 or flt(progress) < 40:
        return "Critical"
    if overdue_actions > 0 or stale_checkins > 0 or flt(progress) < 70:
        return "Watch"
    return "Healthy"
def build_metrics(objectives, action_items) -> dict:
    return {
        "company_progress": average([row.progress for row in objectives]),
        "objectives_on_track": len([row for row in objectives if is_active_objective(row) and flt(row.progress) >= 70]),
        "departments_at_risk": 0,
        "blocked_objectives": len({row.parent_objective for row in action_items if row.status == "Blocked" and row.parent_objective}),
        "overdue_action_items": len([row for row in action_items if is_overdue(row)]),
    }


def build_department_performance(objectives, key_results, action_items) -> list[dict]:
    kr_count_by_department = Counter((row.department or "Unassigned") for row in key_results)
    blocked_by_department = Counter((row.department or "Unassigned") for row in action_items if row.status == "Blocked")
    grouped = defaultdict(list)
    for row in objectives:
        grouped[row.department or "Unassigned"].append(row)

    rows = []
    for department, items in grouped.items():
        progress = average([row.progress for row in items])
        confidence = average([row.confidence for row in items if row.confidence not in (None, "")])
        rows.append({
            "department": department,
            "owner": most_common([row.owner_user for row in items if row.owner_user]) or "",
            "objectives": len(items),
            "key_results": kr_count_by_department.get(department, 0),
            "progress": progress,
            "confidence": confidence,
            "blocked_items": blocked_by_department.get(department, 0),
            "status": department_status(progress, blocked_by_department.get(department, 0)),
        })
    return sorted(rows, key=lambda row: (row["progress"], -row["blocked_items"]))


def build_department_comparison(department_rows) -> list[dict]:
    return sorted(
        [{"department": row["department"], "progress": row["progress"], "status": row["status"]} for row in department_rows],
        key=lambda row: row["progress"],
        reverse=True,
    )


def build_attention_required(objectives, action_items, checkins) -> list[dict]:
    recent_cutoff = getdate(add_days(today(), -7))
    recent_objectives = {
        row.objective for row in checkins
        if row.objective and row.checkin_date and getdate(row.checkin_date) >= recent_cutoff
    }
    objective_by_name = {row.name: row for row in objectives}
    attention = {}

    def add_once(key, source, objective, reason, priority):
        if key and key not in attention:
            attention[key] = attention_row(source, objective, reason, priority)

    for row in action_items:
        objective = objective_by_name.get(row.parent_objective)
        if row.status == "Blocked":
            add_once(row.parent_objective or row.name, row, objective, "Blocked action item", row.priority or "Critical")

    for row in objectives:
        if row.status == "On Hold":
            add_once(row.name, row, row, "Objective on hold", row.priority or "High")
        elif is_active_objective(row) and row.name not in recent_objectives:
            add_once(row.name, row, row, "No check-in in last 7 days", "Medium")
        elif is_active_objective(row) and flt(row.progress) < 50:
            add_once(row.name, row, row, "Low progress", row.priority or "High")

    total_count = len(attention)
    capped_list = sorted(
        attention.values(),
        key=lambda item: (priority_rank(item["priority"]), item["days_blocked"]),
        reverse=True,
    )[:5]
    return capped_list, total_count

def build_critical_activity(objectives, action_items, sprints) -> list[dict]:
    rows = []
    for row in objectives:
        if row.status in {"Completed", "Closed"} or flt(row.progress) >= 100:
            rows.append(activity_row("Objective Completed", "OKR Objective", row.name, row.objective_title, row.owner_user, row.modified))
    for row in action_items:
        if row.status == "Blocked":
            rows.append(activity_row("Objective Blocked", "OKR Action Item", row.name, row.action_item_title, row.owner_user, row.modified))
    for row in sprints:
        if row.status in {"Completed", "Closed"}:
            rows.append(activity_row("Plan Archived", "OKR Plan", row.name, row.plan_name, row.owner_user, row.modified))

    return sorted(rows, key=lambda row: row.get("when") or "", reverse=True)[:10]


def build_manager_performance(objectives, action_items) -> list[dict]:
    grouped = defaultdict(list)
    for row in objectives:
        if row.owner_user:
            grouped[row.owner_user].append(row)
    blocked_by_owner = Counter(row.owner_user for row in action_items if row.owner_user and row.status == "Blocked")

    users = list(grouped.keys() | set(blocked_by_owner.keys()))
    full_names = get_user_names(users)
    rows = []
    for user in users:
        user_objectives = grouped.get(user, [])
        rows.append({
            "manager": user,
            "manager_name": full_names.get(user) or user,
            "objectives": len(user_objectives),
            "average_progress": average([row.progress for row in user_objectives]),
            "blocked_items": blocked_by_owner.get(user, 0),
            "confidence": confidence_summary([row.confidence for row in user_objectives if row.confidence not in (None, "")]),
        })
    ranked = sorted(rows, key=lambda row: (row["average_progress"], -row["blocked_items"], row["objectives"]), reverse=True)[:10]
    for index, row in enumerate(ranked, start=1):
        row["ranking"] = index
    return ranked


def average(values) -> float:
    values = [flt(value) for value in values if value not in (None, "")]
    if not values:
        return 0
    return flt(sum(values) / len(values), 2)


def is_active_objective(row) -> bool:
    return row.status not in {"Completed", "Closed", "Archived"}


def is_overdue(row) -> bool:
    return bool(row.due_date and getdate(row.due_date) < getdate(today()) and row.status not in {"Completed", "Cancelled"})


def department_status(progress: float, blocked_items: int = 0) -> str:
    if blocked_items:
        return "Critical"
    if progress >= 80:
        return "Healthy"
    if progress >= 50:
        return "Watch"
    if progress < 30:
        return "Critical"
    return "At Risk"


def attention_row(row, objective, reason, priority) -> dict:
    opened_on = row.modified or row.creation
    return {
        "department": row.get("department") or (objective.get("department") if objective else "") or "Unassigned",
        "objective": (objective.get("objective_title") if objective else "") or row.get("action_item_title") or row.name,
        "owner": (objective.get("owner_user") if objective else "") or row.get("owner_user") or "",
        "progress": flt(objective.get("progress")) if objective else flt(row.get("progress")),
        "reason": reason,
        "days_blocked": max(0, (getdate(today()) - getdate(opened_on)).days) if opened_on else 0,
        "priority": priority or "Medium",
        "doctype": "OKR Objective" if objective else "OKR Action Item",
        "name": objective.name if objective else row.name,
    }


def priority_rank(value: str) -> int:
    return {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}.get(value or "", 0)


def activity_row(kind, doctype, name, title, owner, when) -> dict:
    return {"type": kind, "doctype": doctype, "name": name, "title": title or name, "owner": owner or "", "when": str(when or "")}


def get_user_names(users: list[str]) -> dict:
    if not users:
        return {}
    rows = frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"], limit_page_length=1000)
    return {row.name: row.full_name for row in rows}


def most_common(values: list[str]) -> str:
    if not values:
        return ""
    return Counter(values).most_common(1)[0][0]


def confidence_summary(values: list[str]) -> str:
    if not values:
        return ""
    scores = {"Green": 5, "Yellow": 3, "Red": 1, "Gray": 0}
    numeric = []
    for value in values:
        numeric.append(scores[value] if value in scores else flt(value))
    return str(average(numeric)) if numeric else most_common(values)
