
from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, format_date, getdate, nowdate
from frappe.utils.pdf import get_pdf

ACTIVE_OBJECTIVE_STATUSES = {"Draft", "Submitted", "Approved", "Active", "At Risk"}
ACTIVE_KR_STATUSES = {"Draft", "Submitted", "Approved", "Active", "At Risk"}
CLOSED_OBJECTIVE_STATUSES = {"Completed", "Cancelled", "Archived"}
CLOSED_KR_STATUSES = {"Achieved", "Missed", "Closed"}


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _title(doctype: str, name: str | None, title_field: str) -> str:
	if not name:
		return ""
	return frappe.db.get_value(doctype, name, title_field) or name


def _days_until(date_value: Any) -> int | None:
	if not date_value:
		return None
	return (getdate(date_value) - getdate(nowdate())).days


def _risk_level(progress: float, confidence: float, days_remaining: int | None, stale: bool, low_rating: bool = False) -> str:
	if progress < 50 and confidence <= 2:
		return "Critical"
	if (stale and progress < 70) or low_rating:
		return "High"
	if days_remaining is not None and 0 <= days_remaining <= 14 and progress < 90:
		return "High"
	if progress < 60 or confidence <= 2 or stale:
		return "Medium"
	return "Low"


def _rating_to_five(value: Any) -> float:
    rating = flt(value)
    if rating <= 0:
        return 0.0
    if rating <= 1:
        rating *= 5.0
    return round(min(5.0, rating), 2)


def _rating_display(value: Any) -> str:
    rating = _rating_to_five(value)
    return f"{rating:g}/5" if rating else ""


def _rating_gap(self_rating: Any, manager_rating: Any) -> float:
    self_value = _rating_to_five(self_rating)
    manager_value = _rating_to_five(manager_rating)
    if not self_value or not manager_value:
        return 0.0
    return round(abs(self_value - manager_value), 2)


def _review_rating_recommended_action(self_rating: float, manager_rating: float, overall_rating: float, gap: float) -> str:
    if self_rating and self_rating <= 2:
        return "Discuss blockers with employee."
    if manager_rating and manager_rating <= 2:
        return "Manager should provide detailed feedback and recovery plan."
    if gap >= 2:
        return "Align expectations between employee and manager."
    if overall_rating and overall_rating <= 2:
        return "Schedule objective review follow-up."
    return "Monitor in next OKR review."


def _review_rating_risk_level(self_rating: float, manager_rating: float, overall_rating: float, gap: float) -> str:
    if (manager_rating and manager_rating <= 2) or (self_rating and self_rating <= 2) or gap >= 3:
        return "High"
    if (overall_rating and overall_rating <= 2) or gap >= 2:
        return "Medium"
    return "Low"


def _recommended_action(reasons: list[str], owner: str | None = None) -> str:
	if any("Critical" in r for r in reasons) or {"Low progress", "Low confidence"}.issubset(set(reasons)):
		return "Schedule review with owner and agree recovery plan."
	if "Missed check-in" in reasons or "No recent update" in reasons:
		return "Ask owner for an updated check-in today."
	if "Deadline approaching" in reasons:
		return "Review delivery plan before deadline."
	if "Marked At Risk" in reasons:
		return "Confirm blockers and escalation path."
	if "Low Review Rating" in reasons:
		return "Conduct review to resolve low rating or alignment gap."
	return "Monitor in next OKR review."


def _latest_checkins_by_key_result() -> dict[str, frappe._dict]:
	if not frappe.db.exists("DocType", "OKR Check In"):
		return {}
	fields = ["name", "key_result", "reported_by", "checkin_date", "progress_percent", "confidence"]
	rows = frappe.get_all(
		"OKR Check In",
		fields=fields,
		order_by="checkin_date desc, modified desc",
		limit_page_length=2000,
	)
	latest = {}
	for row in rows:
		if row.key_result and row.key_result not in latest:
			latest[row.key_result] = row
	return latest


def _build_kr_objective_map(latest_by_kr):
	"""Pre-build a map of {kr_name: objective} to avoid N+1 queries in _objective_last_checkin."""
	kr_names = [name for name in latest_by_kr if name]
	if not kr_names:
		return {}
	rows = frappe.get_all("OKR Key Result", filters={"name": ["in", kr_names]}, fields=["name", "objective"])
	return {row.name: row.objective for row in rows}


def _objective_last_checkin(objective, latest_by_kr, kr_objective_map=None):
	latest_date = None
	for kr_name, checkin in latest_by_kr.items():
		if kr_objective_map is not None:
			kr_objective = kr_objective_map.get(kr_name)
		else:
			kr_objective = frappe.db.get_value("OKR Key Result", checkin.key_result, "objective") if checkin.key_result else None
		if kr_objective == objective and checkin.checkin_date:
			if latest_date is None or getdate(checkin.checkin_date) > getdate(latest_date):
				latest_date = checkin.checkin_date
	return latest_date


def _get_objective_rows() -> list[frappe._dict]:
	fields = ["name", "objective_title", "cycle", "company", "department", "owner_user", "status", "progress", "confidence", "end_date", "objective_type", "parent_objective"]
	fields = [field for field in fields if field == "name" or _has_field("OKR Objective", field)]
	return frappe.get_all("OKR Objective", fields=fields, order_by="modified desc", limit_page_length=1000)


def _get_key_result_rows() -> list[frappe._dict]:
	fields = ["name", "key_result_title", "objective", "cycle", "owner_user", "status", "target_progress", "confidence", "end_date"]
	fields = [field for field in fields if field == "name" or _has_field("OKR Key Result", field)]
	return frappe.get_all("OKR Key Result", fields=fields, order_by="modified desc", limit_page_length=2000)


def _health_row(kind: str, record: str, title: str, owner: str | None, cycle: str | None, department: str | None, progress: float, confidence: float, end_date: Any, reasons: list[str]) -> dict[str, Any]:
	days = _days_until(end_date)
	stale = "No recent update" in reasons or "Missed check-in" in reasons
	low_rating = "Low Review Rating" in reasons
	risk_level = _risk_level(progress, confidence, days, stale, low_rating)
	return {
		"type": kind,
		"record": record,
		"title": title,
		"owner": owner,
		"cycle": cycle,
		"cycle_title": _title("OKR Cycle", cycle, "cycle_name") if cycle else "",
		"department": department,
		"progress": round(flt(progress), 2),
		"confidence": round(flt(confidence), 2),
		"end_date": end_date,
		"days_remaining": days,
		"risk_level": risk_level,
		"reasons": list(dict.fromkeys(reasons)),
		"reason": "; ".join(list(dict.fromkeys(reasons))),
		"recommended_action": _recommended_action(reasons, owner),
	}



def get_health_rows() -> list[dict[str, Any]]:
	latest_by_kr = _latest_checkins_by_key_result()
	kr_objective_map = _build_kr_objective_map(latest_by_kr)
	cutoff_7 = getdate(add_days(nowdate(), -7))
	cutoff_14 = getdate(add_days(nowdate(), -14))
	today = getdate(nowdate())
	rows: list[dict[str, Any]] = []

	latest_reviews = {}
	if frappe.db.exists("DocType", "OKR Objective Review"):
		reviews = frappe.get_all(
			"OKR Objective Review",
			filters={"docstatus": ["<", 2]},
			fields=["objective", "self_rating", "manager_rating", "review_date", "modified"],
			order_by="review_date desc, modified desc"
		)
		for r in reviews:
			if r.objective and r.objective not in latest_reviews:
				latest_reviews[r.objective] = r

	for objective in _get_objective_rows():
		if objective.get("status") in CLOSED_OBJECTIVE_STATUSES:
			continue
		progress = flt(objective.get("progress"))
		confidence = flt(objective.get("confidence"))
		days = _days_until(objective.get("end_date"))
		last_checkin = _objective_last_checkin(objective.name, latest_by_kr, kr_objective_map)
		reasons = []
		if objective.get("status") == "At Risk":
			reasons.append("Marked At Risk")
		if progress < 60:
			reasons.append("Low progress")
		if confidence <= 2:
			reasons.append("Low confidence")
		if days is not None and 0 <= days <= 14 and progress < 90:
			reasons.append("Deadline approaching")
		if not last_checkin or getdate(last_checkin) < cutoff_14:
			reasons.append("No recent update")

		# Check review ratings criteria
		review = latest_reviews.get(objective.name)
		if review:
			emp_rating = _rating_to_five(review.self_rating)
			mgr_rating = _rating_to_five(review.manager_rating)
			if (emp_rating > 0 and emp_rating <= 2) or (mgr_rating > 0 and mgr_rating <= 2) or (emp_rating > 0 and mgr_rating > 0 and abs(mgr_rating - emp_rating) >= 2):
				reasons.append("Low Review Rating")

		if reasons:
			rows.append(_health_row("Objective", objective.name, objective.get("objective_title") or objective.name, objective.get("owner_user"), objective.get("cycle"), objective.get("department"), progress, confidence, objective.get("end_date"), reasons))


	for kr in _get_key_result_rows():
		if kr.get("status") in CLOSED_KR_STATUSES:
			continue
		progress = flt(kr.get("target_progress"))
		confidence = flt(kr.get("confidence"))
		days = _days_until(kr.get("end_date"))
		latest = latest_by_kr.get(kr.name)
		reasons = []
		if kr.get("status") == "At Risk":
			reasons.append("Marked At Risk")
		if progress < 50 and confidence <= 2:
			reasons.append("Critical: low progress + low confidence")
		elif progress < 60:
			reasons.append("Low progress")
		if confidence <= 2:
			reasons.append("Low confidence")
		if days is not None and 0 <= days <= 14 and progress < 90:
			reasons.append("Deadline approaching")
		if not latest or not latest.checkin_date or getdate(latest.checkin_date) < cutoff_7:
			reasons.append("Missed check-in")
		if reasons:
			department = frappe.db.get_value("OKR Objective", kr.get("objective"), "department") if kr.get("objective") else None
			rows.append(_health_row("Key Result", kr.name, kr.get("key_result_title") or kr.name, kr.get("owner_user"), kr.get("cycle"), department, progress, confidence, kr.get("end_date"), reasons))

	rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
	return sorted(rows, key=lambda row: (rank.get(row["risk_level"], 9), row.get("days_remaining") if row.get("days_remaining") is not None else 9999, row["progress"]))


def get_department_performance() -> list[dict[str, Any]]:
	buckets = defaultdict(lambda: {"objective_count": 0, "progress_total": 0.0, "confidence_total": 0.0, "at_risk": 0})
	for obj in _get_objective_rows():
		department = obj.get("department") or "No Department"
		buckets[department]["objective_count"] += 1
		buckets[department]["progress_total"] += flt(obj.get("progress"))
		buckets[department]["confidence_total"] += flt(obj.get("confidence"))
		if obj.get("status") == "At Risk" or flt(obj.get("progress")) < 60 or flt(obj.get("confidence")) <= 2:
			buckets[department]["at_risk"] += 1
	rows = []
	for department, values in buckets.items():
		count = values["objective_count"] or 1
		rows.append({
			"department": department,
			"objective_count": values["objective_count"],
			"average_progress": round(values["progress_total"] / count, 2),
			"average_confidence": round(values["confidence_total"] / count, 2),
			"at_risk": values["at_risk"],
		})
	return sorted(rows, key=lambda row: row["average_progress"], reverse=True)


def _cycle_company(cycle: str | None) -> str | None:
	if not cycle:
		return None
	return frappe.db.get_value("OKR Cycle", cycle, "company") if _has_field("OKR Cycle", "company") else None


def _key_results_for_alignment() -> dict[str, list[dict[str, Any]]]:
	buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for kr in _get_key_result_rows():
		objective = kr.get("objective")
		if not objective:
			continue
		buckets[objective].append({
			"type": "Key Result",
			"record": kr.name,
			"title": kr.get("key_result_title") or kr.name,
			"owner": kr.get("owner_user"),
			"status": kr.get("status"),
			"progress": round(flt(kr.get("target_progress")), 2),
			"confidence": round(flt(kr.get("confidence")), 2),
			"end_date": kr.get("end_date"),
		})
	for rows in buckets.values():
		rows.sort(key=lambda row: (row.get("title") or "").lower())
	return buckets


def _objective_alignment_node(objective: frappe._dict, children_by_parent: dict[str, list[frappe._dict]], krs_by_objective: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
	children = [
		_objective_alignment_node(child, children_by_parent, krs_by_objective)
		for child in sorted(children_by_parent.get(objective.name, []), key=lambda row: (row.get("objective_title") or row.name).lower())
	]
	return {
		"type": "Objective",
		"record": objective.name,
		"title": objective.get("objective_title") or objective.name,
		"objective_type": objective.get("objective_type") or "Objective",
		"owner": objective.get("owner_user"),
		"status": objective.get("status"),
		"progress": round(flt(objective.get("progress")), 2),
		"confidence": round(flt(objective.get("confidence")), 2),
		"end_date": objective.get("end_date"),
		"children": children,
		"key_results": krs_by_objective.get(objective.name, []),
	}


@frappe.whitelist()
def get_alignment_tree(cycle: str | None = None) -> list[dict[str, Any]]:
	"""Return Company -> Department -> Objective hierarchy -> Key Results using existing OKR links."""
	objectives = _get_objective_rows()
	if cycle:
		objectives = [row for row in objectives if row.get("cycle") == cycle]
	objective_names = {row.name for row in objectives}
	children_by_parent: dict[str, list[frappe._dict]] = defaultdict(list)
	roots: list[frappe._dict] = []
	for row in objectives:
		parent = row.get("parent_objective")
		if parent and parent in objective_names:
			children_by_parent[parent].append(row)
		else:
			roots.append(row)

	krs_by_objective = _key_results_for_alignment()
	companies: dict[str, dict[str, Any]] = {}
	for root in roots:
		company = root.get("company") or _cycle_company(root.get("cycle")) or "No Company"
		department = root.get("department") or "No Department"
		company_node = companies.setdefault(company, {"company": company, "departments": {}})
		dept_node = company_node["departments"].setdefault(department, {"department": department, "objectives": []})
		dept_node["objectives"].append(_objective_alignment_node(root, children_by_parent, krs_by_objective))

	result = []
	for company, company_node in sorted(companies.items(), key=lambda item: item[0]):
		departments = []
		for department, dept_node in sorted(company_node["departments"].items(), key=lambda item: item[0]):
			dept_node["objectives"].sort(key=lambda row: (row.get("title") or "").lower())
			departments.append(dept_node)
		result.append({"company": company, "departments": departments})
	return result


def get_review_rating_rows(include_normal: bool = True, limit: int | None = None) -> list[dict[str, Any]]:
    if not frappe.db.exists("DocType", "OKR Objective Review"):
        return []

    reviews = frappe.get_all(
        "OKR Objective Review",
        filters={"docstatus": ["<", 2]},
        fields=[
            "name", "objective", "cycle", "reviewer", "self_rating", "manager_rating",
            "rating", "decision", "review_status", "manager_feedback", "review_date", "modified",
        ],
        order_by="review_date desc, modified desc",
        limit_page_length=limit or 2000,
    )

    rows = []
    for review in reviews:
        if not review.objective:
            continue
        self_rating = _rating_to_five(review.self_rating)
        manager_rating = _rating_to_five(review.manager_rating)
        overall_rating = _rating_to_five(review.rating)
        gap = _rating_gap(review.self_rating, review.manager_rating)
        has_issue = (
            (self_rating and self_rating <= 2)
            or (manager_rating and manager_rating <= 2)
            or gap >= 2
        )
        if not has_issue and not include_normal:
            continue

        objective_row = frappe.db.get_value(
            "OKR Objective",
            review.objective,
            ["objective_title", "owner_user", "department"],
            as_dict=True,
        ) or {}
        rows.append({
            "review": review.name,
            "objective": review.objective,
            "objective_title": objective_row.get("objective_title") or review.objective,
            "owner": objective_row.get("owner_user"),
            "department": objective_row.get("department"),
            "cycle": review.cycle,
            "reviewer": review.reviewer,
            "self_rating": self_rating,
            "manager_rating": manager_rating,
            "overall_rating": overall_rating,
            "self_rating_display": _rating_display(review.self_rating),
            "manager_rating_display": _rating_display(review.manager_rating),
            "overall_rating_display": _rating_display(review.rating),
            "rating_gap": gap,
            "decision": review.decision,
            "review_status": review.review_status,
            "manager_feedback": review.manager_feedback,
            "review_date": review.review_date,
            "modified": review.modified,
            "risk_level": _review_rating_risk_level(self_rating, manager_rating, overall_rating, gap),
            "recommended_action": _review_rating_recommended_action(self_rating, manager_rating, overall_rating, gap),
            "has_issue": has_issue,
        })

    rank = {"High": 0, "Medium": 1, "Low": 2}
    return sorted(rows, key=lambda row: (rank.get(row["risk_level"], 9), -row["rating_gap"], row.get("review_date") or "", row["objective_title"]))


def get_review_rating_signals(include_normal: bool = False) -> list[dict[str, Any]]:
    return get_review_rating_rows(include_normal=include_normal)


def get_latest_review_ratings(limit: int = 15) -> list[dict[str, Any]]:
    rows = get_review_rating_rows(include_normal=True)
    rows = sorted(rows, key=lambda row: (row.get("review_date") or "", row.get("modified") or ""), reverse=True)
    return rows[:limit]


def get_review_rating_summary() -> dict[str, Any]:
    rows = get_review_rating_rows(include_normal=True)
    self_ratings = [row["self_rating"] for row in rows if row.get("self_rating")]
    manager_ratings = [row["manager_rating"] for row in rows if row.get("manager_rating")]
    overall_ratings = [row["overall_rating"] for row in rows if row.get("overall_rating")]
    low_rating_count = sum(
        1 for row in rows
        if (row.get("self_rating") and row.get("self_rating") <= 2)
        or (row.get("manager_rating") and row.get("manager_rating") <= 2)
        or (row.get("overall_rating") and row.get("overall_rating") <= 2)
    )
    rating_gap_count = sum(1 for row in rows if flt(row.get("rating_gap")) >= 2)
    issue_count = sum(1 for row in rows if row.get("has_issue"))

    return {
        "total_reviews": len(rows),
        "avg_self_rating": round(sum(self_ratings) / len(self_ratings), 2) if self_ratings else 0.0,
        "avg_manager_rating": round(sum(manager_ratings) / len(manager_ratings), 2) if manager_ratings else 0.0,
        "avg_overall_rating": round(sum(overall_ratings) / len(overall_ratings), 2) if overall_ratings else 0.0,
        "average_rating": round(sum(overall_ratings or manager_ratings or self_ratings) / len(overall_ratings or manager_ratings or self_ratings), 2) if (overall_ratings or manager_ratings or self_ratings) else 0.0,
        "low_rating_count": low_rating_count,
        "rating_gap_count": rating_gap_count,
        "rating_issues_count": issue_count,
    }


def get_action_item_signals(limit: int = 20) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "OKR Action Item"):
		return {"blocked": [], "overdue": [], "due_soon": [], "summary": {"blocked": 0, "overdue": 0, "due_soon": 0, "total_open": 0}}
	today = getdate(nowdate())
	due_soon_date = getdate(add_days(nowdate(), 7))
	rows = frappe.get_all(
		"OKR Action Item",
		fields=["name", "action_item_title", "key_result", "objective", "cycle", "owner_user", "department", "status", "priority", "start_date", "due_date", "blockers", "modified"],
		filters={"status": ["not in", ["Completed", "Cancelled"]]},
		order_by="due_date asc, modified desc",
		limit_page_length=1000,
	)
	for row in rows:
		row["days_remaining"] = _days_until(row.get("due_date"))
		row["key_result_title"] = _title("OKR Key Result", row.get("key_result"), "key_result_title") if row.get("key_result") else ""
		row["objective_title"] = _title("OKR Objective", row.get("objective"), "objective_title") if row.get("objective") else ""
		row["recommended_action"] = "Resolve blocker with owner." if row.get("status") == "Blocked" else "Review execution plan before due date."
	blocked = [row for row in rows if row.get("status") == "Blocked"]
	overdue = [row for row in rows if row.get("due_date") and getdate(row.get("due_date")) < today]
	due_soon = [row for row in rows if row.get("due_date") and today <= getdate(row.get("due_date")) <= due_soon_date]
	return {
		"blocked": blocked[:limit],
		"overdue": overdue[:limit],
		"due_soon": due_soon[:limit],
		"summary": {
			"blocked": len(blocked),
			"overdue": len(overdue),
			"due_soon": len(due_soon),
			"total_open": len(rows),
		},
	}


@frappe.whitelist()
def get_executive_attention() -> dict[str, Any]:
	health_rows = get_health_rows()
	objectives = _get_objective_rows()
	krs = _get_key_result_rows()
	pending_reviews = frappe.db.count("OKR Objective Review", {"review_status": ["in", ["Draft", "Submitted"]]}) if frappe.db.exists("DocType", "OKR Objective Review") else 0
	latest_by_kr = _latest_checkins_by_key_result()
	owner_latest: dict[str, Any] = {}
	for checkin in latest_by_kr.values():
		owner = checkin.reported_by
		if owner and (owner not in owner_latest or getdate(checkin.checkin_date) > getdate(owner_latest[owner])):
			owner_latest[owner] = checkin.checkin_date
	owners = sorted({row.get("owner_user") for row in objectives + krs if row.get("owner_user")})
	inactive_owners = []
	cutoff_14 = getdate(add_days(nowdate(), -14))
	for owner in owners:
		last = owner_latest.get(owner)
		if not last or getdate(last) < cutoff_14:
			inactive_owners.append({"owner": owner, "last_checkin_date": last, "recommended_action": "Ask owner to submit an OKR check-in."})

	critical = [row for row in health_rows if row["risk_level"] == "Critical"]
	at_risk_objectives = [row for row in health_rows if row["type"] == "Objective"]
	upcoming = [row for row in health_rows if row.get("days_remaining") is not None and 0 <= row["days_remaining"] <= 14]
	missed = [row for row in health_rows if "Missed check-in" in row.get("reasons", [])]
	low_confidence = [row for row in health_rows if row["type"] == "Key Result" and row["confidence"] <= 2]
	avg_progress = round(sum(flt(o.get("progress")) for o in objectives) / (len(objectives) or 1), 2)
	departments = get_department_performance()
	action_item_signals = get_action_item_signals()

	recommended = []
	if critical:
		recommended.append("Review critical OKRs with owners today.")
	if missed:
		recommended.append("Send missed check-in reminders to KR owners.")
	if upcoming:
		recommended.append("Review deadline risks for OKRs due in the next 14 days.")
	if inactive_owners:
		recommended.append("Ask inactive owners to update their OKR status.")
	if action_item_signals.get("summary", {}).get("blocked"):
		recommended.append("Review blocked action items with KR owners.")
	if action_item_signals.get("summary", {}).get("overdue"):
		recommended.append("Follow up on overdue action items.")
	if not recommended:
		recommended.append("No urgent OKR attention items detected today.")

	return {
		"generated_on": nowdate(),
		"summary": {
			"todays_attention": len(health_rows),
			"critical_objectives": len(critical),
			"objectives_at_risk": len(at_risk_objectives),
			"upcoming_deadlines": len(upcoming),
			"pending_reviews": pending_reviews,
			"missed_checkins": len(missed),
			"low_confidence_key_results": len(low_confidence),
			"inactive_owners": len(inactive_owners),
			"average_company_progress": avg_progress,
			"top_department": departments[0] if departments else None,
			"lowest_department": departments[-1] if departments else None,
		},
		"critical_objectives": critical[:10],
		"at_risk_objectives": at_risk_objectives[:20],
		"upcoming_deadlines": upcoming[:20],
		"missed_checkins": missed[:20],
		"low_confidence_key_results": low_confidence[:20],
		"inactive_owners": inactive_owners[:20],
		"recommended_actions": recommended,
		"review_rating_signals": get_review_rating_signals(),
		"latest_review_ratings": get_latest_review_ratings(15),
		"review_rating_summary": get_review_rating_summary(),
		"action_item_signals": action_item_signals,
		"department_performance": departments,
		"alignment_tree": get_alignment_tree(),
		"health_rows": health_rows,
	}


EXECUTIVE_REPORT_TEMPLATE = """
<div class="okr-executive-report">
	<style>
		.okr-executive-report {
			font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
			color: #0f172a;
			background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
			padding: 24px;
		}
		.okr-executive-report * { box-sizing: border-box; }
		.okr-executive-report h1,
		.okr-executive-report h2,
		.okr-executive-report h3,
		.okr-executive-report p { margin: 0; }
		.okr-report-shell {
			max-width: 1280px;
			margin: 0 auto;
		}
		.okr-report-header {
			display: flex;
			justify-content: space-between;
			gap: 18px;
			align-items: flex-start;
			padding: 22px 24px;
			border-radius: 22px;
			background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 52%, #0f766e 100%);
			color: #fff;
			box-shadow: 0 18px 50px rgba(15, 23, 42, 0.18);
			margin-bottom: 18px;
		}
		.okr-report-kicker {
			text-transform: uppercase;
			letter-spacing: 0.14em;
			font-size: 11px;
			opacity: 0.75;
			margin-bottom: 8px;
		}
		.okr-report-header h1 {
			font-size: 32px;
			line-height: 1.1;
			margin-bottom: 10px;
		}
		.okr-report-header p {
			font-size: 13px;
			opacity: 0.85;
			max-width: 720px;
		}
		.okr-report-meta {
			display: grid;
			grid-template-columns: repeat(2, minmax(120px, 1fr));
			gap: 10px;
			min-width: 280px;
		}
		.okr-meta-card {
			border-radius: 18px;
			background: rgba(255, 255, 255, 0.14);
			backdrop-filter: blur(8px);
			padding: 14px 16px;
			border: 1px solid rgba(255, 255, 255, 0.18);
		}
		.okr-meta-card .label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: 0.08em;
			opacity: 0.75;
		}
		.okr-meta-card .value {
			font-size: 28px;
			font-weight: 700;
			line-height: 1.1;
			margin-top: 8px;
		}
		.okr-summary-grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
			gap: 12px;
			margin-bottom: 18px;
		}
		.okr-kpi {
			border: 1px solid #dbe3ee;
			background: #fff;
			border-radius: 18px;
			padding: 16px;
			box-shadow: 0 10px 25px rgba(15, 23, 42, 0.05);
		}
		.okr-kpi.emphasis {
			background: linear-gradient(135deg, #0f172a 0%, #0f766e 100%);
			color: #fff;
			border-color: transparent;
		}
		.okr-kpi .label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: 0.08em;
			color: #64748b;
		}
		.okr-kpi.emphasis .label,
		.okr-kpi.emphasis .hint {
			color: rgba(255, 255, 255, 0.78);
		}
		.okr-kpi .value {
			font-size: 30px;
			font-weight: 700;
			line-height: 1.1;
			margin-top: 10px;
		}
		.okr-kpi .hint {
			font-size: 12px;
			color: #64748b;
			margin-top: 8px;
		}
		.okr-spotlight-grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
			gap: 12px;
			margin-bottom: 18px;
		}
		.okr-spotlight {
			border-radius: 18px;
			padding: 16px;
			background: #fff;
			border: 1px solid #dbe3ee;
		}
		.okr-spotlight .title {
			font-size: 12px;
			text-transform: uppercase;
			letter-spacing: 0.08em;
			color: #64748b;
			margin-bottom: 8px;
		}
		.okr-spotlight .value {
			font-size: 22px;
			font-weight: 700;
			margin-bottom: 6px;
		}
		.okr-spotlight .hint {
			font-size: 13px;
			color: #475569;
		}
		.okr-section {
			background: #fff;
			border: 1px solid #dbe3ee;
			border-radius: 20px;
			padding: 18px;
			margin-bottom: 18px;
			box-shadow: 0 10px 25px rgba(15, 23, 42, 0.04);
			break-inside: avoid;
		}
		.okr-section h2 {
			font-size: 18px;
			margin-bottom: 12px;
		}
		.okr-section .section-note {
			font-size: 12px;
			color: #64748b;
			margin-bottom: 14px;
		}
		.okr-department-row {
			padding: 12px 0;
			border-top: 1px solid #e5eaf1;
		}
		.okr-department-row:first-child {
			border-top: 0;
			padding-top: 0;
		}
		.okr-department-head {
			display: flex;
			justify-content: space-between;
			gap: 14px;
			align-items: baseline;
			margin-bottom: 8px;
		}
		.okr-department-head .name {
			font-weight: 600;
			font-size: 15px;
		}
		.okr-department-head .meta {
			font-size: 12px;
			color: #64748b;
			text-align: right;
		}
		.okr-progress {
			height: 10px;
			background: #e2e8f0;
			border-radius: 999px;
			overflow: hidden;
		}
		.okr-progress span {
			display: block;
			height: 100%;
			border-radius: 999px;
			background: linear-gradient(90deg, #2563eb 0%, #10b981 100%);
		}
		.okr-table {
			width: 100%;
			border-collapse: collapse;
		}
		.okr-table th,
		.okr-table td {
			padding: 10px 8px;
			border-bottom: 1px solid #e5eaf1;
			vertical-align: top;
			text-align: left;
			font-size: 13px;
		}
		.okr-table th {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: 0.08em;
			color: #64748b;
		}
		.okr-pill {
			display: inline-block;
			padding: 3px 8px;
			border-radius: 999px;
			font-size: 11px;
			background: #eef2ff;
			color: #3730a3;
			white-space: nowrap;
		}
		.okr-pill.red { background: #fee2e2; color: #991b1b; }
		.okr-pill.orange { background: #ffedd5; color: #9a3412; }
		.okr-pill.yellow { background: #fef9c3; color: #854d0e; }
		.okr-pill.green { background: #dcfce7; color: #166534; }
		.okr-pill.gray { background: #e2e8f0; color: #334155; }
		.okr-pill.critical { background: #fee2e2; color: #991b1b; }
		.okr-pill.high { background: #ffedd5; color: #9a3412; }
		.okr-pill.medium { background: #fef9c3; color: #854d0e; }
		.okr-pill.low { background: #dcfce7; color: #166534; }
		.okr-list {
			margin: 0;
			padding-left: 18px;
		}
		.okr-list li + li { margin-top: 8px; }
		.okr-muted { color: #64748b; }
		.okr-alert {
			border-radius: 16px;
			padding: 14px 16px;
			margin-bottom: 14px;
			background: #fef3c7;
			border: 1px solid #fbbf24;
			color: #854d0e;
		}
		@media print {
			.okr-executive-report {
				padding: 0;
				background: #fff;
			}
			.okr-report-shell {
				max-width: none;
			}
			.okr-section,
			.okr-kpi,
			.okr-spotlight,
			.okr-report-header {
				box-shadow: none;
			}
		}
	</style>
	<div class="okr-report-shell">
		<div class="okr-report-header">
			<div>
				<div class="okr-report-kicker">{{ _("OKR Executive Report") }}{% if company %} &middot; {{ company }}{% endif %}</div>
				<h1>{{ _("OKR Executive Report") }}</h1>
				{% if active_sprint_name %}<p style="font-size:15px;font-weight:600;opacity:0.9;margin-bottom:6px;">{{ active_sprint_name }}</p>{% endif %}
				<p>{{ _("Generated on {0}").format(generated_on_display) }}{% if company %} &middot; {{ company }}{% endif %}</p>
			</div>
			<div class="okr-report-meta">
				<div class="okr-meta-card">
					<div class="label">{{ _("Avg Progress") }}</div>
					<div class="value">{{ summary.average_company_progress or 0 }}%</div>
				</div>
				<div class="okr-meta-card">
					<div class="label">{{ _("Total Objectives") }}</div>
					<div class="value">{{ total_objectives or 0 }}</div>
				</div>
				<div class="okr-meta-card">
					<div class="label">{{ _("At Risk") }}</div>
					<div class="value">{{ summary.objectives_at_risk or 0 }}</div>
				</div>
				<div class="okr-meta-card">
					<div class="label">{{ _("Completed") }}</div>
					<div class="value">{{ completed_objectives or 0 }}</div>
				</div>
			</div>
		</div>

		<div class="okr-summary-grid">
			{% for card in summary_cards %}
			<div class="okr-kpi{% if card.emphasis %} emphasis{% endif %}">
				<div class="label">{{ card.label }}</div>
				<div class="value">{{ card.value }}</div>
				<div class="hint">{{ card.hint }}</div>
			</div>
			{% endfor %}
		</div>

		<div class="okr-spotlight-grid">
			<div class="okr-spotlight">
				<div class="title">{{ _("Top Department") }}</div>
				<div class="value">{{ top_department.department or _("Not available") }}</div>
				<div class="hint">{{ top_department.average_progress or 0 }}% average progress · {{ top_department.at_risk or 0 }} at risk</div>
			</div>
			<div class="okr-spotlight">
				<div class="title">{{ _("Lowest Department") }}</div>
				<div class="value">{{ lowest_department.department or _("Not available") }}</div>
				<div class="hint">{{ lowest_department.average_progress or 0 }}% average progress · {{ lowest_department.at_risk or 0 }} at risk</div>
			</div>
			<div class="okr-spotlight">
				<div class="title">{{ _("Critical Objectives") }}</div>
				<div class="value">{{ critical_objectives|length }}</div>
				<div class="hint">{{ _("Objectives that require immediate leadership attention.") }}</div>
			</div>
		</div>

		{% if critical_objectives|length %}
		<div class="okr-alert">
			<strong>{{ _("Critical priorities") }}:</strong> {{ critical_objectives|length }} {{ _("objectives need immediate attention.") }}
		</div>
		{% endif %}

		{% if department_performance|length %}
		<div class="okr-section">
			<h2>{{ _("Department Performance") }}</h2>
			<div class="section-note">{{ _("Higher bars indicate healthier delivery across objectives in the department.") }}</div>
			{% for department in department_performance %}
			<div class="okr-department-row">
				<div class="okr-department-head">
					<div class="name">{{ department.department }}</div>
					<div class="meta">{{ department.average_progress }}% · {{ department.objective_count }} {{ _("objectives") }} · {{ department.at_risk }} {{ _("at risk") }}</div>
				</div>
				<div class="okr-progress"><span style="width: {{ department.average_progress }}%;"></span></div>
			</div>
			{% endfor %}
		</div>
		{% endif %}

		<div class="okr-section">
			<h2>{{ _("Review Ratings Summary") }}</h2>
			<div class="section-note">{{ _("CTO Overview of objective review ratings.") }}</div>
			
			<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px;">
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Average Employee Self Rating") }}</div>
					<div class="value" style="color: #0f172a; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">★ {{ "%.1f"|format(review_ratings.avg_employee_rating) }} / 5</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ _("Employee self-evaluations across objectives.") }}</div>
				</div>
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Average Manager Rating") }}</div>
					<div class="value" style="color: #2563eb; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">★ {{ "%.1f"|format(review_ratings.avg_manager_rating) }} / 5</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ _("Manager evaluations across objectives.") }}</div>
				</div>
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Rating Difference") }}</div>
					<div class="value" style="color: {% if review_ratings.rating_difference > 0 %}#b45309{% elif review_ratings.rating_difference < 0 %}#dc2626{% else %}#166534{% endif %}; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">
						{% if review_ratings.rating_difference > 0 %}+{% endif %}{{ "%.2f"|format(review_ratings.rating_difference) }}
					</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ _("Manager Rating minus Employee Rating.") }}</div>
				</div>
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Average Overall Rating") }}</div>
					<div class="value" style="color: #0f766e; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">★ {{ "%.1f"|format(review_ratings.avg_overall_rating) }} / 5</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ review_ratings.rating_gap_summary }}</div>
				</div>
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Total Reviews") }}</div>
					<div class="value" style="color: #0f172a; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">{{ review_ratings.total_reviews or 0 }}</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ _("All objective reviews included in rating visibility.") }}</div>
				</div>
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Low Rating Count") }}</div>
					<div class="value" style="color: #dc2626; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">{{ review_ratings.low_rating_count or 0 }}</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ _("Reviews with self, manager, or overall rating at 2 or below.") }}</div>
				</div>
				<div class="okr-kpi" style="box-shadow: none; border: 1px solid #e5eaf1; background: #f8fafc;">
					<div class="label">{{ _("Rating Gap Count") }}</div>
					<div class="value" style="color: #b45309; margin-top: 10px; font-size: 30px; font-weight: 700; line-height: 1.1;">{{ review_ratings.rating_gap_count or 0 }}</div>
					<div class="hint" style="color: #64748b; font-size: 12px; margin-top: 8px;">{{ _("Reviews where self and manager rating differ by 2 or more.") }}</div>
				</div>
			</div>

			<h3 style="font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin-bottom: 12px;">{{ _("Distribution of Ratings") }}</h3>
			<table class="okr-table">
				<thead>
					<tr>
						<th style="width: 150px;">{{ _("Rating") }}</th>
						<th>{{ _("Distribution") }}</th>
						<th style="width: 80px; text-align: right;">{{ _("Count") }}</th>
					</tr>
				</thead>
				<tbody>
					{% for stars, count in review_ratings.distribution %}
					<tr>
						<td><span style="color: #eab308; font-size: 14px;">{{ stars }}</span></td>
						<td style="vertical-align: middle;">
							<div class="okr-progress" style="height: 10px; background: #e2e8f0; border-radius: 999px;">
								<span style="width: {{ review_ratings.distribution_percentages[stars] }}%; background: #ea580c; border-radius: 999px;"></span>
							</div>
						</td>
						<td style="text-align: right; font-weight: 600;">{{ count }}</td>
					</tr>
					{% endfor %}
				</tbody>
			</table>

			<h3 style="font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin: 22px 0 12px;">{{ _("Recent Review Ratings") }}</h3>
			<table class="okr-table">
				<thead>
					<tr>
						<th>{{ _("Objective") }}</th>
						<th>{{ _("Reviewer") }}</th>
						<th>{{ _("Self Rating") }}</th>
						<th>{{ _("Manager Rating") }}</th>
						<th>{{ _("Overall Rating") }}</th>
						<th>{{ _("Gap") }}</th>
						<th>{{ _("Status") }}</th>
					</tr>
				</thead>
				<tbody>
					{% for row in review_ratings.recent_reviews %}
					<tr>
						<td><strong>{{ row.objective_title }}</strong><br><span class="okr-muted">{{ row.objective }}</span></td>
						<td>{{ row.reviewer or _("Unassigned") }}</td>
						<td>{{ row.self_rating_display or _("Not rated") }}</td>
						<td>{{ row.manager_rating_display or _("Not rated") }}</td>
						<td>{{ row.overall_rating_display or _("Not rated") }}</td>
						<td>{{ row.rating_gap }}</td>
						<td>{{ row.review_status or _("Draft") }}</td>
					</tr>
					{% endfor %}
				</tbody>
			</table>
		</div>

		{% if at_risk_objectives|length %}
		<div class="okr-section">
			<h2>{{ _("Objectives at Risk") }}</h2>
			<div class="section-note">{{ _("Objectives with low progress, low confidence, deadline pressure, or stale updates.") }}</div>
			<table class="okr-table">
				<thead>
					<tr>
						<th>{{ _("Title") }}</th>
						<th>{{ _("Owner") }}</th>
						<th>{{ _("Department") }}</th>
						<th>{{ _("Progress") }}</th>
						<th>{{ _("Confidence") }}</th>
						<th>{{ _("Risk") }}</th>
						<th>{{ _("Deadline") }}</th>
						<th>{{ _("Reason") }}</th>
					</tr>
				</thead>
				<tbody>
					{% for row in at_risk_objectives %}
					<tr>
						<td><strong>{{ row.title }}</strong><br><span class="okr-muted">{{ row.record }}</span></td>
						<td>{{ row.owner or _("Unassigned") }}</td>
						<td>{{ row.department or _("No Department") }}</td>
						<td>{{ row.progress }}%</td>
						<td>{{ row.confidence }}</td>
						<td><span class="okr-pill {{ row.risk_level|lower }}">{{ row.risk_level }}</span></td>
						<td>{{ row.days_remaining_display }}<br><span class="okr-muted">{{ row.end_date_display }}</span></td>
						<td>{{ row.reason }}</td>
					</tr>
					{% endfor %}
				</tbody>
			</table>
		</div>
		{% endif %}

		{% if low_confidence_key_results|length %}
		<div class="okr-section">
			<h2>{{ _("Low Confidence Key Results") }}</h2>
			<div class="section-note">{{ _("Low confidence KRs are strong candidates for manager follow-up and recovery planning.") }}</div>
			<table class="okr-table">
				<thead>
					<tr>
						<th>{{ _("Title") }}</th>
						<th>{{ _("Owner") }}</th>
						<th>{{ _("Progress") }}</th>
						<th>{{ _("Confidence") }}</th>
						<th>{{ _("Risk") }}</th>
						<th>{{ _("Action") }}</th>
					</tr>
				</thead>
				<tbody>
					{% for row in low_confidence_key_results %}
					<tr>
						<td><strong>{{ row.title }}</strong><br><span class="okr-muted">{{ row.record }}</span></td>
						<td>{{ row.owner or _("Unassigned") }}</td>
						<td>{{ row.progress }}%</td>
						<td>{{ row.confidence }}</td>
						<td><span class="okr-pill {{ row.risk_level|lower }}">{{ row.risk_level }}</span></td>
						<td>{{ row.recommended_action }}</td>
					</tr>
					{% endfor %}
				</tbody>
			</table>
		</div>
		{% endif %}

		{% if missed_checkins|length %}
		<div class="okr-section">
			<h2>{{ _("Missed Check-ins") }}</h2>
			<div class="section-note">{{ _("These owners have not submitted a recent OKR check-in.") }}</div>
			<ul class="okr-list">
				{% for row in missed_checkins %}
				<li>
					<strong>{{ row.title }}</strong> <span class="okr-muted">({{ row.record }})</span><br>
					{{ _("Owner") }}: {{ row.owner or _("Unassigned") }} · {{ _("Reason") }}: {{ row.reason }} · {{ _("Recommended action") }}: {{ row.recommended_action }}
				</li>
				{% endfor %}
			</ul>
		</div>
		{% endif %}

		{% if upcoming_deadlines|length %}
		<div class="okr-section">
			<h2>{{ _("Upcoming Deadlines") }}</h2>
			<div class="section-note">{{ _("Items due in the next two weeks need active tracking.") }}</div>
			<table class="okr-table">
				<thead>
					<tr>
						<th>{{ _("Title") }}</th>
						<th>{{ _("Owner") }}</th>
						<th>{{ _("Progress") }}</th>
						<th>{{ _("Deadline") }}</th>
						<th>{{ _("Risk") }}</th>
					</tr>
				</thead>
				<tbody>
					{% for row in upcoming_deadlines %}
					<tr>
						<td><strong>{{ row.title }}</strong><br><span class="okr-muted">{{ row.record }}</span></td>
						<td>{{ row.owner or _("Unassigned") }}</td>
						<td>{{ row.progress }}%</td>
						<td>{{ row.days_remaining_display }}<br><span class="okr-muted">{{ row.end_date_display }}</span></td>
						<td><span class="okr-pill {{ row.risk_level|lower }}">{{ row.risk_level }}</span></td>
					</tr>
					{% endfor %}
				</tbody>
			</table>
		</div>
		{% endif %}

		<div class="okr-section">
			<h2>{{ _("Recommended Actions") }}</h2>
			<div class="section-note">{{ _("Suggested next steps for leadership review.") }}</div>
			{% if recommended_actions|length %}
			<ul class="okr-list">
				{% for action in recommended_actions %}
				<li>{{ action }}</li>
				{% endfor %}
			</ul>
			{% else %}
			<p class="okr-muted">{{ _("No urgent actions detected.") }}</p>
			{% endif %}
		</div>

		<div style="margin-top:32px;padding-top:18px;border-top:1px solid #e5eaf1;display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#94a3b8;">
			<div>
				<strong style="color:#64748b;">{{ _("OKR Executive Report") }}</strong>{% if company %} &middot; {{ company }}{% endif %}{% if active_sprint_name %} &middot; {{ active_sprint_name }}{% endif %}
			</div>
			<div>{{ _("Generated") }}: {{ generated_on_display }}</div>
		</div>
	</div>
</div>
"""


def _format_report_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	formatted_rows: list[dict[str, Any]] = []
	for row in rows:
		formatted = dict(row)
		formatted["progress"] = round(flt(formatted.get("progress")), 2)
		formatted["confidence"] = round(flt(formatted.get("confidence")), 2)
		formatted["end_date_display"] = format_date(formatted.get("end_date")) if formatted.get("end_date") else _("No deadline")
		days_remaining = formatted.get("days_remaining")
		if days_remaining is None:
			formatted["days_remaining_display"] = _("Not set")
		elif days_remaining == 0:
			formatted["days_remaining_display"] = _("Due today")
		elif days_remaining == 1:
			formatted["days_remaining_display"] = _("1 day left")
		elif days_remaining > 1:
			formatted["days_remaining_display"] = _("{0} days left").format(days_remaining)
		else:
			formatted["days_remaining_display"] = _("{0} days overdue").format(abs(days_remaining))
		formatted_rows.append(formatted)
	return formatted_rows


def _format_department_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	formatted_rows: list[dict[str, Any]] = []
	for row in rows:
		formatted = dict(row)
		formatted["average_progress"] = round(flt(formatted.get("average_progress")), 2)
		formatted["average_confidence"] = round(flt(formatted.get("average_confidence")), 2)
		formatted["at_risk"] = cint(formatted.get("at_risk"))
		formatted_rows.append(formatted)
	return formatted_rows




def _get_company_and_sprint():
	"""Return (company_name, active_sprint_name) for the executive report header."""
	company = ""
	active_sprint_name = ""
	try:
		if _has_field("OKR Cycle", "company"):
			cycle_row = frappe.db.get_value(
				"OKR Cycle",
				{"status": ["in", ["Active", "Draft"]]},
				["cycle_name", "company"],
				order_by="modified desc",
				as_dict=True,
			)
			if cycle_row:
				active_sprint_name = cycle_row.get("cycle_name") or ""
				company = cycle_row.get("company") or ""
		if not company:
			company = frappe.defaults.get_global_default("company") or ""
		if not company:
			company = frappe.db.get_value("Company", {}, "name") or ""
		if not active_sprint_name and _has_field("OKR Cycle", "cycle_name"):
			active_sprint_name = frappe.db.get_value("OKR Cycle", {}, "cycle_name", order_by="modified desc") or ""
	except Exception:
		pass
	return company, active_sprint_name

def get_review_ratings_summary() -> dict[str, Any]:
	if not frappe.db.exists("DocType", "OKR Objective Review"):
		return {
			"avg_employee_rating": 0.0,
				"avg_manager_rating": 0.0,
			"avg_overall_rating": 0.0,
			"avg_rating_gap": 0.0,
			"total_reviews": 0,
			"low_rating_count": 0,
			"rating_gap_count": 0,
			"recent_reviews": [],
			"rating_gap_summary": "No rating gap data available.",
			"rating_difference": 0.0,
			"distribution": [("★★★★★", 0), ("★★★★", 0), ("★★★", 0), ("★★", 0), ("★", 0)],
			"distribution_percentages": {"★★★★★": 0, "★★★★": 0, "★★★": 0, "★★": 0, "★": 0}
		}

	reviews = frappe.get_all(
		"OKR Objective Review",
		filters={"docstatus": ["<", 2]},
		fields=["objective", "manager_rating", "self_rating", "rating", "review_date", "modified"],
		order_by="review_date desc, modified desc"
	)

	latest_reviews = {}
	for r in reviews:
		obj = r.objective
		if obj not in latest_reviews:
			latest_reviews[obj] = r

	manager_ratings = [_rating_to_five(r.manager_rating) for r in latest_reviews.values() if _rating_to_five(r.manager_rating) > 0]
	employee_ratings = [_rating_to_five(r.self_rating) for r in latest_reviews.values() if _rating_to_five(r.self_rating) > 0]
	overall_ratings = [_rating_to_five(r.rating) for r in latest_reviews.values() if _rating_to_five(r.rating) > 0]
	rating_gaps = [_rating_gap(r.self_rating, r.manager_rating) for r in latest_reviews.values() if _rating_gap(r.self_rating, r.manager_rating) > 0]

	avg_manager = sum(manager_ratings) / len(manager_ratings) if manager_ratings else 0.0
	avg_employee = sum(employee_ratings) / len(employee_ratings) if employee_ratings else 0.0
	avg_overall = sum(overall_ratings) / len(overall_ratings) if overall_ratings else 0.0
	avg_gap = sum(rating_gaps) / len(rating_gaps) if rating_gaps else 0.0
	difference = avg_manager - avg_employee

	distribution_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
	for r in latest_reviews.values():
		if r.manager_rating:
			rating_val = int(round(_rating_to_five(r.manager_rating)))
			if rating_val in distribution_counts:
				distribution_counts[rating_val] += 1

	total_with_manager_rating = len(manager_ratings) or 1

	stars_map = {
		5: "★★★★★",
		4: "★★★★",
		3: "★★★",
		2: "★★",
		1: "★"
	}

	review_summary = get_review_rating_summary()
	recent_reviews = sorted(get_review_rating_rows(include_normal=True, limit=10), key=lambda row: row.get("review_date") or "", reverse=True)

	distribution = []
	distribution_percentages = {}
	for stars_num in [5, 4, 3, 2, 1]:
		count = distribution_counts[stars_num]
		pct = (count / total_with_manager_rating) * 100
		stars_str = stars_map[stars_num]
		distribution.append((stars_str, count))
		distribution_percentages[stars_str] = pct

	return {
		"avg_employee_rating": avg_employee,
		"avg_manager_rating": avg_manager,
		"avg_overall_rating": avg_overall,
		"avg_rating_gap": avg_gap,
		"total_reviews": review_summary.get("total_reviews", 0),
		"low_rating_count": review_summary.get("low_rating_count", 0),
		"rating_gap_count": review_summary.get("rating_gap_count", 0),
		"recent_reviews": recent_reviews,
		"rating_gap_summary": f"Average self-manager gap is {avg_gap:.2f} points across reviewed objectives.",
		"rating_difference": difference,
		"distribution": distribution,
		"distribution_percentages": distribution_percentages
	}


def _build_executive_report_context() -> dict[str, Any]:
	report = get_executive_attention()
	summary = report.get("summary") or {}
	department_performance = _format_department_rows(report.get("department_performance") or [])
	critical_objectives = _format_report_rows(report.get("critical_objectives") or [])
	at_risk_objectives = _format_report_rows(report.get("at_risk_objectives") or [])
	low_confidence_key_results = _format_report_rows(report.get("low_confidence_key_results") or [])
	missed_checkins = _format_report_rows(report.get("missed_checkins") or [])
	upcoming_deadlines = _format_report_rows(report.get("upcoming_deadlines") or [])
	top_department = department_performance[0] if department_performance else {}
	lowest_department = department_performance[-1] if department_performance else {}

	company, active_sprint_name = _get_company_and_sprint()

	# Objective count breakdown
	all_objectives = _get_objective_rows()
	total_objectives = len(all_objectives)
	active_objectives = sum(1 for o in all_objectives if o.get("status") in ACTIVE_OBJECTIVE_STATUSES)
	completed_objectives = sum(1 for o in all_objectives if o.get("status") == "Completed")

	summary_cards = [
		{
			"label": _("Today's Attention"),
			"value": summary.get("todays_attention", 0),
			"hint": _("Items requiring leadership review."),
			"emphasis": True,
		},
		{
			"label": _("Total Objectives"),
			"value": total_objectives,
			"hint": _("All objectives across all sprints."),
		},
		{
			"label": _("Active Objectives"),
			"value": active_objectives,
			"hint": _("Currently in-flight objectives."),
		},
		{
			"label": _("Completed"),
			"value": completed_objectives,
			"hint": _("Objectives fully achieved."),
		},
		{
			"label": _("Critical Objectives"),
			"value": summary.get("critical_objectives", 0),
			"hint": _("Most urgent escalations."),
		},
		{
			"label": _("Objectives at Risk"),
			"value": summary.get("objectives_at_risk", 0),
			"hint": _("Objectives with active risk signals."),
		},
		{
			"label": _("Missed Check-ins"),
			"value": summary.get("missed_checkins", 0),
			"hint": _("Owners need follow-up."),
		},
		{
			"label": _("Low Confidence KRs"),
			"value": summary.get("low_confidence_key_results", 0),
			"hint": _("Potential recovery candidates."),
		},
		{
			"label": _("Upcoming Deadlines"),
			"value": summary.get("upcoming_deadlines", 0),
			"hint": _("Due in the next 14 days."),
		},
		{
			"label": _("Pending Reviews"),
			"value": summary.get("pending_reviews", 0),
			"hint": _("Review queue still open."),
		},
		{
			"label": _("Average Company Progress"),
			"value": f"{summary.get('average_company_progress', 0)}%",
			"hint": _("Portfolio progress across all objectives."),
			"emphasis": True,
		},
	]

	return {
		"generated_on_display": format_date(report.get("generated_on") or nowdate()),
		"company": company,
		"active_sprint_name": active_sprint_name,
		"summary": summary,
		"summary_cards": summary_cards,
		"total_objectives": total_objectives,
		"active_objectives": active_objectives,
		"completed_objectives": completed_objectives,
		"top_department": top_department,
		"lowest_department": lowest_department,
		"department_performance": department_performance,
		"critical_objectives": critical_objectives,
		"at_risk_objectives": at_risk_objectives,
		"low_confidence_key_results": low_confidence_key_results,
		"missed_checkins": missed_checkins,
		"upcoming_deadlines": upcoming_deadlines,
		"recommended_actions": report.get("recommended_actions") or [],
		"review_ratings": get_review_ratings_summary(),
	}



def _render_executive_report_html() -> str:
	return frappe.render_template(EXECUTIVE_REPORT_TEMPLATE, _build_executive_report_context())


@frappe.whitelist()
def get_executive_report_preview() -> dict[str, Any]:
	return {
		"title": _("OKR Executive Report"),
		"html": _render_executive_report_html(),
	}


@frappe.whitelist()
def download_executive_report_pdf() -> None:
	html = _render_executive_report_html()
	frappe.local.response.filename = "okr-executive-report.pdf"
	frappe.local.response.filecontent = get_pdf(html, {"orientation": "Landscape", "load-error-handling": "ignore"})
	frappe.local.response.type = "pdf"
