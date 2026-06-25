
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import frappe
from frappe.utils import add_days, flt, getdate

from okr_management.utils.okr_calculations import get_current_value_from_progress

DEMO_MARKER = "[OKR_DEMO_DATA_V2]"
OLD_DEMO_MARKERS = ("[OKR_DEMO_DATA_V1]",)
DEMO_COMPANY = "Demo Company"
DEMO_COMPANY_ABBR = "DEMO"
DEPARTMENTS = ["Sales", "HR", "Product", "Support", "Operations", "Marketing"]

DEMO_USERS = {
	"Sales": ["sales.manager@example.com", "sales.lead@example.com", "sales.executive@example.com"],
	"HR": ["hr.manager@example.com", "hr.lead@example.com", "hr.specialist@example.com"],
	"Product": ["product.manager@example.com", "product.lead@example.com", "product.owner@example.com"],
	"Support": ["support.manager@example.com", "support.lead@example.com", "support.engineer@example.com"],
	"Operations": ["operations.manager@example.com", "operations.lead@example.com", "operations.analyst@example.com"],
	"Marketing": ["marketing.manager@example.com", "marketing.lead@example.com", "marketing.specialist@example.com"],
}

CYCLES = {
	"Q1 2026 OKR Cycle": ("2026-01-01", "2026-03-31"),
	"Q2 2026 OKR Cycle": ("2026-04-01", "2026-06-24"),
	"May 2026 Recovery Sprint": ("2026-05-01", "2026-05-31"),
	"June 2026 Executive Focus": ("2026-06-01", "2026-06-24"),
}

OVERALL_RATING_RULE = "Manager-entered final rating; demo values are calibrated against self and manager ratings."


@dataclass(frozen=True)
class KRSpec:
	title: str
	metric_type: str
	baseline: float
	target: float
	progress: float
	unit: str
	confidence: str
	scenario: str = "on_track"
	checkins: int = 3
	stale: bool = False
	missed: bool = False


@dataclass(frozen=True)
class ObjectiveSpec:
	title: str
	department: str
	cycle: str
	objective_type: str
	priority: str
	scenario: str
	level: str
	parent_title: str | None
	krs: tuple[KRSpec, ...]


OBJECTIVES: tuple[ObjectiveSpec, ...] = (
	ObjectiveSpec(
		"Drive company-wide revenue and growth", "Sales", "Q1 2026 OKR Cycle", "Company", "Strategic", "completed", "company", None,
		(
			KRSpec("Close Q1 ARR target", "Currency", 6_000_000, 9_000_000, 100, "INR", "5", "completed", 4),
			KRSpec("Increase net revenue retention", "Percentage", 88, 96, 100, "%", "5", "completed", 4),
			KRSpec("Expand to 3 new enterprise verticals", "Count", 0, 3, 100, "verticals", "5", "completed", 4),
		),
	),
	ObjectiveSpec(
		"Build company culture and talent foundation", "HR", "Q1 2026 OKR Cycle", "Company", "High", "completed", "company", None,
		(
			KRSpec("Complete all-hands OKR kickoff", "Count", 0, 1, 100, "events", "5", "completed", 4),
			KRSpec("Achieve 90%+ eNPS score", "Percentage", 72, 90, 96, "%", "5", "completed", 4),
			KRSpec("Hire 12 key positions across departments", "Count", 2, 12, 100, "hires", "5", "completed", 4),
		),
	),
	ObjectiveSpec(
		"Establish Marketing as a revenue driver", "Marketing", "Q1 2026 OKR Cycle", "Company", "Strategic", "completed", "company", None,
		(
			KRSpec("Generate 1200 marketing qualified leads", "Count", 400, 1200, 100, "MQLs", "5", "completed", 4),
			KRSpec("Launch brand refresh initiative", "Count", 0, 1, 100, "campaigns", "5", "completed", 4),
			KRSpec("Achieve 3x campaign ROI", "Ratio", 1.2, 3.0, 100, "x", "5", "completed", 4),
		),
	),
	ObjectiveSpec(
		"Operational Excellence — Q1 Foundation", "Operations", "Q1 2026 OKR Cycle", "Company", "High", "completed", "company", None,
		(
			KRSpec("Reduce process bottlenecks by 40%", "Percentage", 0, 40, 100, "%", "5", "completed", 4),
			KRSpec("Implement OKR tracking system", "Count", 0, 1, 100, "systems", "5", "completed", 4),
			KRSpec("Achieve 95% vendor SLA compliance", "Percentage", 78, 95, 98, "%", "5", "completed", 4),
		),
	),
	ObjectiveSpec(
		"Achieve predictable enterprise growth", "Sales", "Q2 2026 OKR Cycle", "Company", "Strategic", "at_risk", "company", None,
		(
			KRSpec("Close enterprise ARR pipeline", "Currency", 8_000_000, 12_000_000, 52, "INR", "2", "at_risk", 3, stale=True),
			KRSpec("Improve lead-to-opportunity conversion", "Percentage", 18, 30, 46, "%", "2", "critical", 2, missed=True),
			KRSpec("Expand strategic account coverage", "Count", 45, 80, 70, "accounts", "3", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Build a high-performing employee experience", "HR", "Q2 2026 OKR Cycle", "Company", "High", "on_track", "company", None,
		(
			KRSpec("Reduce voluntary attrition", "Percentage", 14, 9, 78, "%", "4", "on_track", 3),
			KRSpec("Complete manager capability workshops", "Count", 0, 30, 100, "sessions", "5", "completed", 4),
			KRSpec("Improve engagement survey score", "Count", 68, 82, 72, "score", "4", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Increase enterprise revenue", "Sales", "May 2026 Recovery Sprint", "Department", "Strategic", "on_track", "department", "Achieve predictable enterprise growth",
		(
			KRSpec("Generate qualified enterprise pipeline", "Currency", 18_000_000, 30_000_000, 82, "INR", "4", "on_track", 3),
			KRSpec("Improve proposal win rate", "Percentage", 24, 36, 76, "%", "4", "on_track", 3),
			KRSpec("Launch executive account plans", "Count", 4, 18, 90, "plans", "5", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Reduce hiring turnaround time", "HR", "May 2026 Recovery Sprint", "Department", "High", "at_risk", "department", "Build a high-performing employee experience",
		(
			KRSpec("Reduce time-to-offer", "Count", 34, 21, 48, "days", "2", "critical", 2, stale=True),
			KRSpec("Improve offer acceptance rate", "Percentage", 68, 84, 55, "%", "2", "at_risk", 2, missed=True),
			KRSpec("Build interview panel coverage", "Percentage", 35, 90, 66, "%", "3", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Improve product delivery predictability", "Product", "May 2026 Recovery Sprint", "Department", "Strategic", "on_track", "department", None,
		(
			KRSpec("Deliver committed roadmap items", "Percentage", 40, 90, 84, "%", "4", "on_track", 4),
			KRSpec("Reduce escaped production defects", "Count", 28, 10, 72, "defects", "3", "on_track", 3),
			KRSpec("Increase sprint predictability", "Percentage", 62, 88, 80, "%", "4", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Improve customer satisfaction", "Support", "Q2 2026 OKR Cycle", "Department", "Strategic", "completed", "department", None,
		(
			KRSpec("Increase CSAT score", "Percentage", 82, 92, 100, "%", "5", "completed", 4),
			KRSpec("Reduce first response time", "Count", 6, 2, 100, "hours", "5", "completed", 4),
			KRSpec("Improve first-contact resolution", "Percentage", 64, 78, 96, "%", "5", "completed", 4),
		),
	),
	ObjectiveSpec(
		"Reduce support backlog", "Support", "May 2026 Recovery Sprint", "Team", "High", "at_risk", "team", "Improve customer satisfaction",
		(
			KRSpec("Reduce aged open tickets", "Count", 120, 35, 40, "tickets", "2", "critical", 2, stale=True),
			KRSpec("Publish self-service help content", "Count", 8, 45, 58, "articles", "3", "at_risk", 2),
			KRSpec("Improve SLA compliance", "Percentage", 74, 92, 44, "%", "2", "critical", 2, missed=True),
		),
	),
	ObjectiveSpec(
		"Improve operational efficiency", "Operations", "Q2 2026 OKR Cycle", "Department", "High", "on_track", "department", None,
		(
			KRSpec("Reduce process cycle time", "Count", 12, 7, 75, "days", "4", "on_track", 3),
			KRSpec("Automate recurring operations tasks", "Percentage", 20, 75, 82, "%", "4", "on_track", 4),
			KRSpec("Improve vendor SLA adherence", "Percentage", 70, 90, 68, "%", "3", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Reduce operational delays", "Operations", "May 2026 Recovery Sprint", "Team", "High", "delayed", "team", "Improve operational efficiency",
		(
			KRSpec("Reduce delayed purchase requests", "Count", 64, 18, 42, "requests", "2", "critical", 2, stale=True),
			KRSpec("Improve issue resolution SLA", "Percentage", 61, 88, 52, "%", "2", "at_risk", 2),
			KRSpec("Complete process audit actions", "Count", 5, 30, 60, "actions", "3", "on_track", 2),
		),
	),
	ObjectiveSpec(
		"Increase qualified inbound pipeline", "Marketing", "May 2026 Recovery Sprint", "Department", "Strategic", "on_track", "department", None,
		(
			KRSpec("Increase marketing qualified leads", "Count", 900, 1500, 88, "MQLs", "4", "on_track", 3),
			KRSpec("Improve campaign ROI", "Ratio", 2.4, 4.0, 79, "x", "4", "on_track", 3),
			KRSpec("Launch account-based campaigns", "Count", 2, 8, 75, "campaigns", "4", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Improve brand-to-demand conversion", "Marketing", "June 2026 Executive Focus", "Team", "High", "no_recent_updates", "team", "Increase qualified inbound pipeline",
		(
			KRSpec("Increase website visitor-to-lead rate", "Percentage", 1.8, 3.2, 50, "%", "2", "at_risk", 1, stale=True),
			KRSpec("Grow webinar sourced opportunities", "Count", 20, 75, 38, "opportunities", "2", "critical", 1, missed=True),
			KRSpec("Improve nurture email conversion", "Percentage", 4, 8, 56, "%", "3", "at_risk", 1),
		),
	),
	ObjectiveSpec(
		"Improve Product onboarding activation", "Product", "June 2026 Executive Focus", "Team", "High", "on_track", "team", "Improve product delivery predictability",
		(
			KRSpec("Increase activation rate", "Percentage", 48, 70, 74, "%", "4", "on_track", 2),
			KRSpec("Reduce onboarding drop-offs", "Percentage", 32, 18, 65, "%", "3", "on_track", 2),
			KRSpec("Ship guided setup improvements", "Count", 0, 6, 83, "features", "4", "on_track", 2),
		),
	),
	ObjectiveSpec(
		"Improve individual sales execution", "Sales", "May 2026 Recovery Sprint", "Individual", "Medium", "on_track", "individual", "Increase enterprise revenue",
		(
			KRSpec("Complete strategic account meetings", "Count", 4, 20, 90, "meetings", "5", "on_track", 3),
			KRSpec("Update CRM next steps weekly", "Percentage", 40, 95, 86, "%", "4", "on_track", 3),
		),
	),
	ObjectiveSpec(
		"Improve support engineer ownership", "Support", "May 2026 Recovery Sprint", "Individual", "Medium", "at_risk", "individual", "Reduce support backlog",
		(
			KRSpec("Resolve assigned aged tickets", "Count", 8, 35, 35, "tickets", "2", "critical", 1, stale=True),
			KRSpec("Maintain documentation updates", "Count", 2, 12, 50, "updates", "2", "at_risk", 1, missed=True),
		),
	),
	ObjectiveSpec(
		"Improve HR specialist hiring cadence", "HR", "May 2026 Recovery Sprint", "Individual", "Medium", "on_track", "individual", "Reduce hiring turnaround time",
		(
			KRSpec("Complete recruiter screen SLAs", "Percentage", 60, 95, 78, "%", "4", "on_track", 3),
			KRSpec("Build talent pool for critical roles", "Count", 20, 80, 72, "candidates", "4", "on_track", 3),
		),
	),
)


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _append_marker(text: str | None) -> str:
	text = text or ""
	return text if DEMO_MARKER in text else f"{text}\n{DEMO_MARKER}".strip()


def _safe_insert(doc: Any) -> str:
	doc.insert(ignore_permissions=True)
	return doc.name


def _get_or_create_company() -> str:
	if frappe.db.exists("Company", DEMO_COMPANY):
		return DEMO_COMPANY
	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": DEMO_COMPANY,
			"abbr": DEMO_COMPANY_ABBR,
			"default_currency": "INR" if frappe.db.exists("Currency", "INR") else "USD",
			"country": "India" if frappe.db.exists("Country", "India") else frappe.db.get_value("Country", {}, "name"),
		}
	)
	return _safe_insert(company)


def _get_or_create_department(department_name: str, company: str) -> str:
	name = frappe.db.get_value("Department", {"department_name": department_name, "company": company}, "name")
	if name:
		return name
	department = frappe.get_doc(
		{"doctype": "Department", "department_name": department_name, "company": company, "is_group": 0, "disabled": 0}
	)
	return _safe_insert(department)


def _ensure_user(email: str, full_name: str) -> str:
	if frappe.db.exists("User", email):
		return email
	try:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name.split()[0],
				"last_name": " ".join(full_name.split()[1:]) or "User",
				"full_name": full_name,
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		)
		user.flags.no_welcome_mail = True
		return _safe_insert(user)
	except Exception:
		return "Administrator"


def _ensure_employee(user: str, department: str, company: str, full_name: str) -> None:
	if user == "Administrator" or frappe.db.exists("Employee", {"user_id": user}):
		return
	try:
		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": full_name.split()[0],
				"last_name": " ".join(full_name.split()[1:]) or "User",
				"user_id": user,
				"company": company,
				"department": department,
				"status": "Active",
				"date_of_joining": "2024-04-01",
				"gender": "Other" if frappe.db.exists("Gender", "Other") else None,
			}
		)
		employee.insert(ignore_permissions=True)
	except Exception:
		# Employee master data varies across ERPNext installs. Demo OKRs can still use the User safely.
		pass


def _get_demo_users(company: str, departments: dict[str, str]) -> dict[str, list[str]]:
	users: dict[str, list[str]] = {}
	for department, emails in DEMO_USERS.items():
		users[department] = []
		for email in emails:
			full_name = email.split("@")[0].replace(".", " ").title()
			user = _ensure_user(email, full_name)
			users[department].append(user)
			_ensure_employee(user, departments[department], company, full_name)
	return users


def _owner_for(users: dict[str, list[str]], department: str, level: str, index: int = 0) -> str:
	pool = users.get(department) or ["Administrator"]
	if level == "company":
		return pool[0]
	if level == "department":
		return pool[0]
	if level == "team":
		return pool[min(1, len(pool) - 1)]
	return pool[(2 + index) % len(pool)] if pool else "Administrator"


def _find_marked_doc(doctype: str, filters: dict[str, Any], marker_field: str) -> str | None:
	if not _has_field(doctype, marker_field):
		return None
	return frappe.db.get_value(doctype, {**filters, marker_field: ["like", f"%{DEMO_MARKER}%"]}, "name")


def _get_or_create_cycle(cycle_name: str, company: str, owner: str) -> str:
	name = _find_marked_doc("OKR Cycle", {"cycle_name": cycle_name, "company": company}, "description")
	if name:
		return name
	start_date, end_date = CYCLES[cycle_name]
	cycle = frappe.get_doc(
		{
			"doctype": "OKR Cycle",
			"cycle_name": cycle_name,
			"company": company,
			"cycle_type": "Quarterly",
			"start_date": start_date,
			"end_date": end_date,
			"review_deadline": add_days(end_date, 7),
			"owner_user": owner,
			"status": "Active",
			"description": _append_marker("Enterprise demo OKR cycle for CTO dashboards and executive insights."),
		}
	)
	return _safe_insert(cycle)


def _status_for_progress(progress: float, completed_label: str, active_label: str = "Active") -> str:
	if flt(progress) >= 100:
		return completed_label
	if flt(progress) < 60:
		return "At Risk"
	return active_label


def _find_parent(created: dict[str, str], title: str | None) -> str | None:
	return created.get(title or "")


def _get_or_create_objective(spec: ObjectiveSpec, company: str, department: str, cycle: str, owner: str, parent: str | None) -> str:
	name = _find_marked_doc("OKR Objective", {"objective_title": spec.title, "cycle": cycle}, "description")
	if name:
		return name
	start_date, end_date = frappe.db.get_value("OKR Cycle", cycle, ["start_date", "end_date"])
	objective = frappe.get_doc(
		{
			"doctype": "OKR Objective",
			"objective_title": spec.title,
			"cycle": cycle,
			"company": company,
			"department": department,
			"owner_user": owner,
			"parent_objective": parent,
			"objective_type": spec.objective_type,
			"priority": spec.priority,
			"start_date": start_date,
			"end_date": end_date,
			"status": "Draft",
			"progress": 0,
			"confidence": "3",
			"description": _append_marker(f"Demo {spec.level} objective. Scenario: {spec.scenario}."),
		}
	)
	return _safe_insert(objective)


def _get_or_create_key_result(objective: str, cycle: str, owner: str, kr: KRSpec, weight: float) -> str:
	name = _find_marked_doc("OKR Key Result", {"key_result_title": kr.title, "objective": objective}, "description")
	if name:
		return name
	start_date, end_date = frappe.db.get_value("OKR Cycle", cycle, ["start_date", "end_date"])
	current = get_current_value_from_progress(kr.baseline, kr.target, kr.progress)
	key_result = frappe.get_doc(
		{
			"doctype": "OKR Key Result",
			"key_result_title": kr.title,
			"objective": objective,
			"cycle": cycle,
			"owner_user": owner,
			"metric_type": kr.metric_type,
			"baseline_value": kr.baseline,
			"target_value": kr.target,
			"current_value": current,
			"target_progress": kr.progress,
			"weight": weight,
			"unit_of_measure": kr.unit,
			"start_date": start_date,
			"end_date": end_date,
			"status": _status_for_progress(kr.progress, "Achieved", "Active"),
			"confidence": kr.confidence,
			"description": _append_marker(f"Demo KR scenario: {kr.scenario}. Baseline {kr.baseline}, target {kr.target} {kr.unit}."),
		}
	)
	return _safe_insert(key_result)


def _checkin_dates(cycle: str, count: int, stale: bool = False, missed: bool = False) -> list[str]:
	start, end = frappe.db.get_value("OKR Cycle", cycle, ["start_date", "end_date"])
	start = getdate(start)
	end = getdate(end)
	if stale:
		base_dates = ["2026-05-07", "2026-05-21", "2026-06-03"]
		return [str(max(start, min(getdate(d), end))) for d in base_dates[:count]]
	if missed:
		base_dates = ["2026-06-01", "2026-06-08"]
		return [str(max(start, min(getdate(d), end))) for d in base_dates[:count]]
	span = max((end - start).days, 1)
	return [str(add_days(start, min(span, 7 + idx * max(7, span // max(count, 1))))) for idx in range(count)]


def _progress_series(final_progress: float, count: int, scenario: str) -> list[float]:
	final = flt(final_progress)
	if count <= 1:
		return [final]
	if scenario in {"critical", "at_risk"}:
		start = max(5, final - 12)
	elif scenario == "completed":
		start = max(40, final - 45)
	else:
		start = max(10, final - 35)
	step = (final - start) / (count - 1)
	return [round(start + step * idx, 2) for idx in range(count)]


def _get_or_create_checkins(key_result: str, objective: str, cycle: str, owner: str, kr: KRSpec) -> list[str]:
	existing = frappe.get_all(
		"OKR Check In",
		filters={"key_result": key_result, "notes": ["like", f"%{DEMO_MARKER}%"]},
		pluck="name",
		order_by="checkin_date asc",
	)
	if len(existing) >= kr.checkins:
		return existing

	dates = _checkin_dates(cycle, kr.checkins, stale=kr.stale, missed=kr.missed)
	progress_values = _progress_series(kr.progress, kr.checkins, kr.scenario)
	names = list(existing)
	for idx in range(len(existing), kr.checkins):
		progress = progress_values[idx]
		confidence = kr.confidence if idx == kr.checkins - 1 else str(max(1, min(5, int(flt(kr.confidence)) + (0 if kr.scenario in {"critical", "at_risk"} else -1))))
		checkin = frappe.get_doc(
			{
				"doctype": "OKR Check In",
				"key_result": key_result,
				"objective": objective,
				"cycle": cycle,
				"reported_by": owner,
				"checkin_date": dates[idx],
				"progress_percent": progress,
				"self_rating": max(1, min(5, round(flt(confidence)))),
				"manager_rating": max(1, min(5, round(flt(confidence)))),
				"manager_feedback": "Reviewed in demo cadence. Follow-up required." if flt(confidence) <= 2 else "Progress reviewed as on track.",
				"review_status": "Approved" if progress >= 60 else "Submitted",
				"confidence": confidence,
				"blockers": "Blocked by cross-functional dependency." if flt(confidence) <= 2 else "",
				"notes": _append_marker(f"Demo check-in: {kr.scenario}, progress {progress}%."),
				"status": "Reviewed" if progress >= 60 else "Submitted",
			}
		)
		_safe_insert(checkin)
		names.append(checkin.name)
	return names



def _action_item_plan(kr: KRSpec) -> list[dict[str, str]]:
    base = [
        {"title": f"Prepare execution plan for {kr.title}", "status": "Completed", "priority": "Medium", "offset": 2},
        {"title": f"Coordinate owner follow-up for {kr.title}", "status": "In Progress", "priority": "High", "offset": 14},
    ]
    if kr.scenario == "completed":
        return [
            {"title": f"Complete enablement for {kr.title}", "status": "Completed", "priority": "Medium", "offset": 4},
            {"title": f"Validate final outcome for {kr.title}", "status": "Completed", "priority": "Medium", "offset": 18},
        ]
    if kr.scenario == "critical":
        return base + [
            {"title": f"Resolve blocker for {kr.title}", "status": "Blocked", "priority": "Critical", "offset": 24},
            {"title": f"Agree recovery actions for {kr.title}", "status": "Not Started", "priority": "High", "offset": 32},
        ]
    if kr.scenario == "at_risk":
        return base + [
            {"title": f"Review risk mitigation for {kr.title}", "status": "Blocked", "priority": "High", "offset": 28},
        ]
    return base + [
        {"title": f"Publish weekly update for {kr.title}", "status": "Not Started", "priority": "Medium", "offset": 30},
    ]


def _bounded_action_dates(cycle: str, offset: int, status: str) -> tuple[str, str, str | None]:
    start, end = frappe.db.get_value("OKR Cycle", cycle, ["start_date", "end_date"])
    start = getdate(start)
    end = getdate(end)
    span = max((end - start).days, 1)
    start_date = add_days(start, min(max(offset, 0), max(span - 1, 0)))
    due_date = add_days(start_date, 10)
    if due_date > end:
        due_date = end
    if status == "Completed":
        completion_date = add_days(start_date, 8)
        if completion_date > due_date:
            completion_date = due_date
        return str(start_date), str(due_date), str(completion_date)
    return str(start_date), str(due_date), None


def _get_or_create_action_items(key_result: str, objective: str, cycle: str, owner: str, department: str, kr: KRSpec) -> list[str]:
    if not frappe.db.exists("DocType", "OKR Action Item"):
        return []
    existing = frappe.get_all(
        "OKR Action Item",
        filters={"key_result": key_result, "notes": ["like", f"%{DEMO_MARKER}%"]},
        pluck="name",
        order_by="creation asc",
    )
    plan = _action_item_plan(kr)
    if len(existing) >= len(plan):
        return existing

    names = list(existing)
    for item in plan[len(existing):]:
        start_date, due_date, completion_date = _bounded_action_dates(cycle, int(item["offset"]), item["status"])
        blockers = "Dependency needs leadership unblock." if item["status"] == "Blocked" else ""
        doc = frappe.get_doc(
            {
                "doctype": "OKR Action Item",
                "action_item_title": item["title"],
                "key_result": key_result,
                "objective": objective,
                "cycle": cycle,
                "owner_user": owner,
                "department": department,
                "status": item["status"],
                "priority": item["priority"],
                "start_date": start_date,
                "due_date": due_date,
                "completion_date": completion_date,
                "notes": _append_marker(f"Demo action item supporting KR: {kr.title}."),
                "blockers": blockers,
            }
        )
        _safe_insert(doc)
        names.append(doc.name)
    return names

def _review_rating_profile(scenario: str, index: int) -> tuple[float, float, float]:
	profiles = {
		"completed": [(5, 4, 4.5), (4.5, 4.5, 4.5), (5, 5, 5), (4.5, 4, 4.25)],
		"on_track": [(4, 3, 3.5), (4.5, 4, 4.25), (5, 3, 4), (4, 4, 4), (4.5, 3.5, 4)],
		"at_risk": [(4, 2, 3), (3, 2, 2.5), (3.5, 2.5, 3), (4, 3, 3.5), (5, 2, 3.5)],
		"critical": [(2, 2, 2), (3, 1, 2), (2.5, 1.5, 2), (3, 2, 2.5), (2, 1, 1.5)],
		"delayed": [(3.5, 2.5, 3), (4, 2, 3), (3, 2, 2.5)],
		"no_recent_updates": [(4, 3, 3.5), (3.5, 2.5, 3), (4.5, 3, 3.75)],
	}
	options = profiles.get(scenario, profiles["on_track"])
	return options[index % len(options)]


def _rating_feedback(self_rating: float, manager_rating: float, overall_rating: float) -> str:
	if abs(self_rating - manager_rating) >= 2:
		return "Self and manager assessment differ; align expectations."
	if manager_rating <= 2.5 or overall_rating <= 2.5:
		return "Needs recovery plan and closer manager review."
	if overall_rating < 4:
		return "Good progress, but needs follow-up on blockers."
	return "Strong execution and good progress."


def _get_or_create_review(objective: str, cycle: str, reviewer: str, title: str, progress: float, confidence: float, scenario: str, index: int, review_label: str = "Final", review_offset_days: int = -3) -> str:
	name = frappe.db.get_value(
		"OKR Objective Review",
		{"objective": objective, "cycle": cycle, "summary": ["like", f"%{review_label}%{DEMO_MARKER}%"]},
		"name",
	)
	if name:
		return name
	self_rating, manager_rating, overall_rating = _review_rating_profile(scenario, index)
	review_status = "Approved" if progress >= 75 else "Modified" if progress >= 50 else "Rejected"
	decision = "Approve" if progress >= 75 else "Approve with Conditions" if progress >= 50 else "Defer"
	review = frappe.get_doc(
		{
			"doctype": "OKR Objective Review",
			"objective": objective,
			"cycle": cycle,
			"reviewer": reviewer,
			"review_date": add_days(frappe.db.get_value("OKR Cycle", cycle, "end_date"), review_offset_days),
			"self_rating": round(self_rating / 5, 2),
			"manager_rating": round(manager_rating / 5, 2),
			"manager_feedback": _rating_feedback(self_rating, manager_rating, overall_rating),
			"review_status": review_status,
			"rating": round(overall_rating / 5, 2),
			"decision": decision,
			"summary": _append_marker(f"{review_label} review summary for {title}."),
			"risks": "Needs management attention: progress, confidence, or update cadence is weak." if progress < 60 or confidence <= 2 else "Healthy execution cadence.",
			"next_actions": "Schedule owner review and agree recovery plan." if progress < 60 or confidence <= 2 else "Continue weekly execution cadence.",
		}
	)
	return _safe_insert(review)


def _recalculate(key_results: list[str], objectives: list[str]) -> None:
	try:
		from okr_management.utils.okr_calculations import recalculate_from_key_result, recalculate_objective_progress
	except Exception:
		return
	for key_result in key_results:
		recalculate_from_key_result(key_result)
	for objective in objectives:
		recalculate_objective_progress(objective)


@frappe.whitelist()
def create_demo_data() -> dict[str, Any]:
	"""Create realistic, idempotent V2 OKR demo data for CTO demos."""
	counts = defaultdict(int)
	created_objectives: dict[str, str] = {}
	all_objectives: list[str] = []
	all_key_results: list[str] = []
	all_action_items: list[str] = []
	try:
		company = _get_or_create_company()
		counts["company"] = 1
		departments = {name: _get_or_create_department(name, company) for name in DEPARTMENTS}
		counts["departments"] = len(departments)
		users = _get_demo_users(company, departments)
		counts["demo_users"] = sum(len(v) for v in users.values())

		cycle_owner = next(iter(users.values()))[0] if users else "Administrator"
		cycles = {name: _get_or_create_cycle(name, company, cycle_owner) for name in CYCLES}
		counts["cycles"] = len(cycles)

		for index, spec in enumerate(OBJECTIVES):
			owner = _owner_for(users, spec.department, spec.level, index)
			cycle = cycles[spec.cycle]
			department = departments[spec.department]
			parent = _find_parent(created_objectives, spec.parent_title)
			objective = _get_or_create_objective(spec, company, department, cycle, owner, parent)
			created_objectives[spec.title] = objective
			all_objectives.append(objective)
			counts["objectives"] += 1

			weight = round(100 / len(spec.krs), 2)
			for kr in spec.krs:
				key_result = _get_or_create_key_result(objective, cycle, owner, kr, weight)
				all_key_results.append(key_result)
				counts["key_results"] += 1
				counts["checkins"] += len(_get_or_create_checkins(key_result, objective, cycle, owner, kr))
				created_actions = _get_or_create_action_items(key_result, objective, cycle, owner, department, kr)
				all_action_items.extend(created_actions)
				counts["action_items"] += len(created_actions)

		_recalculate(all_key_results, all_objectives)

		for index, spec in enumerate(OBJECTIVES):
			objective = created_objectives[spec.title]
			progress, confidence, cycle = frappe.db.get_value("OKR Objective", objective, ["progress", "confidence", "cycle"])
			reviewer = _owner_for(users, spec.department, "department", 1)
			_get_or_create_review(objective, cycle, reviewer, spec.title, flt(progress), flt(confidence), spec.scenario, index)
			counts["reviews"] += 1

		frappe.db.commit()
		return {
			"status": "success",
			"message": "OKR V2 demo organization is ready. Existing marked demo records were reused.",
			"marker": DEMO_MARKER,
			"company": company,
			"counts": dict(counts),
		}
	except Exception:
		frappe.db.rollback()
		raise


@frappe.whitelist()
def clear_demo_data() -> dict[str, Any]:
	"""Remove OKR transaction data so CTO demos start from one clean professional dataset.

	Master data such as users, company, and departments is retained. Overall Rating
	follows the manager-entered final rating rule used by OKR Objective Review.
	"""
	deleted = defaultdict(int)
	try:
		for doctype in (
			"OKR Action Item",
			"OKR Check In",
			"OKR Objective Review",
			"OKR Key Result",
			"OKR Objective",
			"OKR Cycle",
		):
			if not frappe.db.exists("DocType", doctype):
				continue
			names = frappe.get_all(doctype, pluck="name")
			for name in names:
				frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
				deleted[doctype] += 1
		frappe.db.commit()
		return {
			"status": "success",
			"message": "All OKR transaction records removed. Demo users, company, and departments were retained safely.",
			"rating_rule": OVERALL_RATING_RULE,
			"deleted": dict(deleted),
		}
	except Exception:
		frappe.db.rollback()
		raise
