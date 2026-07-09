# Copyright (c) 2026, Ajanta Bottles and contributors
# For license information, please see license.txt

from __future__ import annotations

from collections import Counter, defaultdict

import frappe
from frappe.utils import add_days, cint, flt, getdate, today


no_cache = 1


def get_context(context):
    context.no_cache = 1


@frappe.whitelist()
def get_filter_options() -> dict:
    years = frappe.get_all(
        "Fiscal Year",
        fields=["name"],
        order_by="year_start_date desc",
        limit_page_length=50,
    )
    sprints = frappe.get_all(
        "OKR Sprint",
        fields=["name", "sprint_name", "financial_year", "financial_quarter", "status"],
        order_by="start_date desc, modified desc",
        limit_page_length=200,
    )
    departments = frappe.get_all(
        "Department",
        fields=["name", "department_name"],
        order_by="department_name asc",
        limit_page_length=500,
    )
    owners = get_owner_options()
    return {
        "years": years,
        "quarters": ["Q1", "Q2", "Q3", "Q4"],
        "sprints": sprints,
        "departments": departments,
        "owners": owners,
        "statuses": ["Draft", "Planned", "Active", "On Hold", "Completed", "Closed", "Archived"],
    }


@frappe.whitelist()
def get_dashboard_data(
    year: str | None = None,
    quarter: str | None = None,
    sprint: str | None = None,
    department: str | None = None,
    owner: str | None = None,
    status: str | None = None,
) -> dict:
    filters = scrub_filters(year, quarter, sprint, department, owner, status)
    sprint_names = get_sprint_names(filters)
    plan_names = get_plan_names(filters, sprint_names)

    plans = get_plans(filters, plan_names)
    sprints = get_sprints(filters, sprint_names)
    objectives = get_objectives(filters, sprint_names, plan_names)
    key_results = get_key_results(filters, sprint_names, plan_names, [row.name for row in objectives])
    action_items = get_action_items(filters, sprint_names, plan_names, [row.name for row in objectives], [row.name for row in key_results])
    checkins = get_checkins(filters, sprint_names, plan_names, [row.name for row in objectives], [row.name for row in key_results])

    return {
        "filters": filters,
        "metrics": build_metrics(plans, sprints, objectives, key_results, action_items, checkins),
        "department_performance": build_department_performance(objectives, key_results),
        "at_risk": build_at_risk(objectives, action_items, checkins),
        "latest_activity": build_latest_activity(objectives, action_items, sprints, checkins),
        "top_performers": build_top_performers(objectives, checkins),
        "charts": build_charts(objectives, sprints, checkins),
        "updated_at": frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
    }


def scrub_filters(year, quarter, sprint, department, owner, status) -> dict:
    return {
        "year": year or "",
        "quarter": quarter or "",
        "sprint": sprint or "",
        "department": department or "",
        "owner": owner or "",
        "status": status or "",
    }


def get_owner_options() -> list[dict]:
    owners = set()
    sources = [
        ("OKR Objective", "owner_user"),
        ("OKR Key Result", "owner_user"),
        ("OKR Action Item", "owner_user"),
        ("OKR Check In", "reported_by"),
    ]
    for doctype, fieldname in sources:
        rows = frappe.get_all(doctype, fields=[fieldname], limit_page_length=1000)
        owners.update(row.get(fieldname) for row in rows if row.get(fieldname))
    if not owners:
        return []
    users = frappe.get_all(
        "User",
        filters={"name": ["in", list(owners)]},
        fields=["name", "full_name"],
        order_by="full_name asc",
        limit_page_length=1000,
    )
    return users


def get_sprint_names(filters: dict) -> list[str] | None:
    if filters.get("sprint"):
        return [filters["sprint"]]
    sprint_filters = {}
    if filters.get("year"):
        sprint_filters["financial_year"] = filters["year"]
    if filters.get("quarter"):
        sprint_filters["financial_quarter"] = filters["quarter"]
    if filters.get("department"):
        sprint_filters["department"] = filters["department"]
    if filters.get("owner"):
        sprint_filters["sprint_owner"] = filters["owner"]
    if not sprint_filters:
        return None
    return frappe.get_all("OKR Sprint", filters=sprint_filters, pluck="name", limit_page_length=1000)


def get_plan_names(filters: dict, sprint_names: list[str] | None) -> list[str] | None:
    if filters.get("quarter") or filters.get("sprint"):
        if not sprint_names:
            return []
        return frappe.get_all(
            "OKR Sprint",
            filters={"name": ["in", sprint_names]},
            pluck="parent_plan",
            limit_page_length=1000,
        )
    return None


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
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "name", plan_names)
    return frappe.get_all(
        "OKR Plan",
        filters=doc_filters,
        fields=["name", "plan_name", "financial_year", "department", "owner_user", "status", "progress", "modified", "creation"],
        limit_page_length=5000,
    )


def get_sprints(filters: dict, sprint_names: list[str] | None) -> list[dict]:
    doc_filters = {}
    add_common_filters(doc_filters, filters, owner_field="sprint_owner")
    apply_names_filter(doc_filters, "name", sprint_names)
    return frappe.get_all(
        "OKR Sprint",
        filters=doc_filters,
        fields=["name", "sprint_name", "parent_plan", "financial_year", "financial_quarter", "department", "sprint_owner", "status", "progress", "modified", "creation"],
        limit_page_length=5000,
    )


def get_objectives(filters: dict, sprint_names: list[str] | None, plan_names: list[str] | None) -> list[dict]:
    doc_filters = {}
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "sprint", sprint_names)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    return frappe.get_all(
        "OKR Objective",
        filters=doc_filters,
        fields=["name", "objective_title", "sprint", "parent_plan", "financial_year", "department", "owner_user", "status", "progress", "confidence", "modified", "creation"],
        order_by="progress desc, modified desc",
        limit_page_length=10000,
    )


def get_key_results(filters: dict, sprint_names: list[str] | None, plan_names: list[str] | None, objective_names: list[str]) -> list[dict]:
    doc_filters = {}
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "parent_sprint", sprint_names)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    if filters.get("status"):
        doc_filters["status"] = filters["status"]
    if objective_names:
        doc_filters["objective"] = ["in", objective_names]
    elif sprint_names is not None or plan_names is not None or filters.get("department") or filters.get("owner") or filters.get("status"):
        doc_filters["objective"] = ["in", ["__none__"]]
    return frappe.get_all(
        "OKR Key Result",
        filters=doc_filters,
        fields=["name", "key_result_title", "objective", "parent_plan", "parent_sprint", "financial_year", "department", "owner_user", "status", "target_progress", "modified", "creation"],
        limit_page_length=20000,
    )


def get_action_items(filters: dict, sprint_names: list[str] | None, plan_names: list[str] | None, objective_names: list[str], kr_names: list[str]) -> list[dict]:
    doc_filters = {"status": ["!=", "Cancelled"]}
    if filters.get("status"):
        doc_filters["status"] = filters["status"]
    add_common_filters(doc_filters, filters)
    apply_names_filter(doc_filters, "parent_sprint", sprint_names)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    if objective_names:
        doc_filters["parent_objective"] = ["in", objective_names]
    if kr_names:
        doc_filters["parent_key_result"] = ["in", kr_names]
    elif sprint_names is not None or plan_names is not None or filters.get("department") or filters.get("owner") or filters.get("status"):
        doc_filters["parent_key_result"] = ["in", ["__none__"]]
    return frappe.get_all(
        "OKR Action Item",
        filters=doc_filters,
        fields=["name", "action_item_title", "parent_key_result", "parent_objective", "parent_sprint", "parent_plan", "financial_year", "department", "owner_user", "status", "progress", "due_date", "modified", "creation"],
        order_by="due_date asc, modified desc",
        limit_page_length=20000,
    )


def get_checkins(filters: dict, sprint_names: list[str] | None, plan_names: list[str] | None, objective_names: list[str], kr_names: list[str]) -> list[dict]:
    doc_filters = {"status": "Submitted"}
    if filters.get("year"):
        doc_filters["financial_year"] = filters["year"]
    if filters.get("department"):
        doc_filters["department"] = filters["department"]
    if filters.get("owner"):
        doc_filters["reported_by"] = filters["owner"]
    apply_names_filter(doc_filters, "parent_sprint", sprint_names)
    apply_names_filter(doc_filters, "parent_plan", plan_names)
    if objective_names:
        doc_filters["objective"] = ["in", objective_names]
    if kr_names:
        doc_filters["key_result"] = ["in", kr_names]
    elif sprint_names is not None or plan_names is not None or filters.get("department") or filters.get("owner"):
        doc_filters["key_result"] = ["in", ["__none__"]]
    return frappe.get_all(
        "OKR Check In",
        filters=doc_filters,
        fields=["name", "checkin_date", "reported_by", "key_result", "objective", "parent_plan", "parent_sprint", "department", "progress", "confidence", "blockers", "modified", "creation"],
        order_by="checkin_date desc, creation desc",
        limit_page_length=20000,
    )


def build_metrics(plans, sprints, objectives, key_results, action_items, checkins) -> dict:
    objective_progress = [flt(row.progress) for row in objectives]
    active_statuses = {"Active", "In Progress", "Planned"}
    completed_statuses = {"Completed", "Closed"}
    return {
        "total_plans": len(plans),
        "active_plans": count_status(plans, active_statuses),
        "active_sprints": count_status(sprints, active_statuses),
        "total_objectives": len(objectives),
        "total_key_results": len(key_results),
        "total_action_items": len(action_items),
        "total_checkins": len(checkins),
        "organization_progress": average(objective_progress),
        "completed_objectives": len([row for row in objectives if row.status in completed_statuses or flt(row.progress) >= 100]),
        "at_risk_objectives": len([row for row in objectives if is_active_objective(row) and flt(row.progress) < 50]),
        "blocked_action_items": len([row for row in action_items if row.status == "Blocked"]),
        "overdue_action_items": len([row for row in action_items if is_overdue(row)]),
    }


def build_department_performance(objectives, key_results) -> list[dict]:
    kr_count_by_department = Counter((row.department or "Unassigned") for row in key_results)
    grouped = defaultdict(list)
    for row in objectives:
        grouped[row.department or "Unassigned"].append(row)
    rows = []
    for department, items in grouped.items():
        progress = average([flt(row.progress) for row in items])
        confidence = average([flt(row.confidence) for row in items if row.confidence not in (None, "")])
        rows.append({
            "department": department,
            "progress": progress,
            "objectives": len(items),
            "key_results": kr_count_by_department.get(department, 0),
            "confidence": confidence,
            "status": department_status(progress, items),
        })
    return sorted(rows, key=lambda row: row["progress"], reverse=True)


def build_at_risk(objectives, action_items, checkins) -> list[dict]:
    recent_cutoff = getdate(add_days(today(), -7))
    recent_objectives = {row.objective for row in checkins if row.objective and row.checkin_date and getdate(row.checkin_date) >= recent_cutoff}
    rows = []
    for row in objectives:
        if is_active_objective(row) and flt(row.progress) < 50:
            rows.append(risk_row("Objective below 50%", row, "OKR Objective", row.objective_title, f"{flt(row.progress, 1)}% progress", "high"))
        if is_active_objective(row) and row.name not in recent_objectives:
            rows.append(risk_row("No check-in in last 7 days", row, "OKR Objective", row.objective_title, row.owner_user or "", "medium"))
        if row.confidence not in (None, "") and flt(row.confidence) <= 2:
            rows.append(risk_row("Low confidence objective", row, "OKR Objective", row.objective_title, f"Confidence {row.confidence}", "high"))
    for row in action_items:
        if row.status == "Blocked":
            rows.append(risk_row("Blocked action item", row, "OKR Action Item", row.action_item_title, row.owner_user or "", "critical"))
        if is_overdue(row):
            rows.append(risk_row("Overdue action item", row, "OKR Action Item", row.action_item_title, str(row.due_date), "high"))
    return sorted(rows, key=lambda row: severity_rank(row["severity"]), reverse=True)[:75]


def build_latest_activity(objectives, action_items, sprints, checkins) -> list[dict]:
    rows = []
    for row in objectives:
        rows.append(activity_row("New Objective created", "OKR Objective", row.name, row.objective_title, row.owner_user, row.creation))
        if row.status in {"Completed", "Closed"} or flt(row.progress) >= 100:
            rows.append(activity_row("Objective completed", "OKR Objective", row.name, row.objective_title, row.owner_user, row.modified))
    for row in checkins:
        rows.append(activity_row("Check-In submitted", "OKR Check In", row.name, row.objective or row.key_result, row.reported_by, row.creation))
    for row in action_items:
        if row.status == "Blocked":
            rows.append(activity_row("Action Item blocked", "OKR Action Item", row.name, row.action_item_title, row.owner_user, row.modified))
    for row in sprints:
        if row.status in {"Completed", "Closed"}:
            rows.append(activity_row("Sprint completed", "OKR Sprint", row.name, row.sprint_name, row.sprint_owner, row.modified))
    return sorted(rows, key=lambda row: row.get("when") or "", reverse=True)[:30]


def build_top_performers(objectives, checkins) -> list[dict]:
    completed_by_owner = Counter()
    for row in objectives:
        if row.owner_user and (row.status in {"Completed", "Closed"} or flt(row.progress) >= 100):
            completed_by_owner[row.owner_user] += 1

    grouped = defaultdict(list)
    for row in checkins:
        if row.reported_by:
            grouped[row.reported_by].append(row)

    user_names = list(grouped.keys() | completed_by_owner.keys())
    full_names = get_user_names(user_names)
    rows = []
    for user in user_names:
        user_checkins = grouped.get(user, [])
        departments = [row.department for row in user_checkins if row.department]
        rows.append({
            "employee": user,
            "employee_name": full_names.get(user) or user,
            "department": most_common(departments) or "",
            "completed_objectives": completed_by_owner.get(user, 0),
            "average_progress": average([flt(row.progress) for row in user_checkins]),
            "confidence": confidence_summary([row.confidence for row in user_checkins if row.confidence]),
            "checkins": len(user_checkins),
        })
    return sorted(rows, key=lambda row: (row["completed_objectives"], row["average_progress"], row["checkins"]), reverse=True)[:20]


def build_charts(objectives, sprints, checkins) -> dict:
    return {
        "progress_by_department": [
            {"label": row["department"], "value": row["progress"]}
            for row in build_department_performance(objectives, [])
        ],
        "objective_status_distribution": counter_chart([row.status or "Unspecified" for row in objectives]),
        "monthly_checkins": monthly_chart(checkins, "checkin_date"),
        "sprint_completion_trend": monthly_chart([row for row in sprints if row.status in {"Completed", "Closed"}], "modified"),
        "confidence_distribution": counter_chart([str(row.confidence) for row in objectives if row.confidence not in (None, "")]),
    }


def count_status(rows, statuses: set[str]) -> int:
    return len([row for row in rows if row.status in statuses])


def average(values) -> float:
    values = [flt(value) for value in values if value not in (None, "")]
    if not values:
        return 0
    return flt(sum(values) / len(values), 2)


def is_active_objective(row) -> bool:
    return row.status not in {"Completed", "Closed", "Archived"}


def is_overdue(row) -> bool:
    return bool(row.due_date and getdate(row.due_date) < getdate(today()) and row.status not in {"Completed", "Cancelled"})


def department_status(progress: float, objectives) -> str:
    if any(is_active_objective(row) and flt(row.progress) < 50 for row in objectives):
        return "At Risk"
    if progress >= 80:
        return "On Track"
    if progress >= 50:
        return "Watch"
    return "At Risk"


def risk_row(kind, row, doctype, title, detail, severity) -> dict:
    return {
        "type": kind,
        "doctype": doctype,
        "name": row.name,
        "title": title or row.name,
        "detail": detail or "",
        "department": row.get("department") or "",
        "owner": row.get("owner_user") or "",
        "severity": severity,
    }


def severity_rank(value: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(value, 0)


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
        if value in scores:
            numeric.append(scores[value])
        else:
            numeric.append(flt(value))
    return str(average(numeric)) if numeric else most_common(values)


def counter_chart(values: list[str]) -> list[dict]:
    counts = Counter(value or "Unspecified" for value in values)
    return [{"label": label, "value": count} for label, count in counts.most_common()]


def monthly_chart(rows, fieldname: str) -> list[dict]:
    counts = Counter()
    for row in rows:
        value = row.get(fieldname)
        if not value:
            continue
        date_value = getdate(value)
        counts[f"{date_value.year}-{date_value.month:02d}"] += 1
    return [{"label": label, "value": counts[label]} for label in sorted(counts.keys())]
