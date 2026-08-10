from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate, nowdate


def _has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _avg(doctype: str, fieldname: str, filters: dict | None = None) -> float:
	if not _has_field(doctype, fieldname):
		return 0.0
	row = frappe.get_all(doctype, fields=[f"avg({fieldname}) as value"], filters=filters or {}, limit=1)
	return flt(row[0].value if row else 0, 2)


@frappe.whitelist()
def average_objective_progress() -> float:
	return _avg("OKR Objective", "progress")


@frappe.whitelist()
def average_objective_confidence() -> float:
	return _avg("OKR Objective", "confidence")


@frappe.whitelist()
def pending_reviews_count() -> int:
	if not _has_field("OKR Objective Review", "review_status"):
		return 0
	return frappe.db.count("OKR Objective Review", {"review_status": ["in", ["Draft", "Submitted"]]})


@frappe.whitelist()
def checkins_this_month_count() -> int:
	filters = {}
	if _has_field("OKR Check In", "checkin_date"):
		filters["checkin_date"] = [">=", get_first_day(nowdate())]
	return frappe.db.count("OKR Check In", filters)


@frappe.whitelist()
def average_review_rating() -> str:
	if not frappe.db.exists("DocType", "OKR Objective Review"):
		return "★ 0.0 / 5"
	reviews = frappe.get_all(
		"OKR Objective Review",
		filters={"manager_rating": [">", 0], "docstatus": ["<", 2]},
		fields=["objective", "manager_rating", "review_date", "modified"],
		order_by="review_date desc, modified desc"
	)
	latest_ratings = {}
	for r in reviews:
		obj = r.objective
		if obj not in latest_ratings:
			latest_ratings[obj] = flt(r.manager_rating) * 5.0

	if not latest_ratings:
		return "★ 0.0 / 5"

	avg_rating = sum(latest_ratings.values()) / len(latest_ratings)
	return f"★ {avg_rating:.1f} / 5"



@frappe.whitelist()
def get_executive_insights(days_without_update: int = 14, risk_progress: float = 60, risk_confidence: float = 3) -> dict:
	cutoff = add_days(nowdate(), -int(days_without_update))
	today = getdate(nowdate())
	near_end = add_days(nowdate(), 14)

	objectives = frappe.get_all(
		"OKR Objective",
		fields=["name", "objective_title", "owner_user", "status", "progress", "confidence", "end_date"],
		order_by="modified desc",
		limit_page_length=500,
	)
	key_results = frappe.get_all(
		"OKR Key Result",
		fields=["name", "key_result_title", "objective", "assignee", "status", "target_progress", "confidence", "end_date", "modified"],
		order_by="modified desc",
		limit_page_length=500,
	)

	at_risk_objectives = []
	for objective in objectives:
		reasons = []
		if flt(objective.progress) < risk_progress and objective.status not in {"Completed", "Archived", "Cancelled"}:
			reasons.append(_("progress below {0}%").format(risk_progress))
		if flt(objective.confidence) < risk_confidence:
			reasons.append(_("low confidence"))
		if objective.end_date and today <= getdate(objective.end_date) <= getdate(near_end) and flt(objective.progress) < 90:
			reasons.append(_("end date is near"))
		if objective.status == "At Risk":
			reasons.append(_("marked At Risk"))
		if reasons:
			at_risk_objectives.append({**objective, "reasons": list(dict.fromkeys(reasons))})

	key_results_need_attention = []
	for kr in key_results:
		reasons = []
		if flt(kr.target_progress) < risk_progress and kr.status not in {"Achieved", "Closed"}:
			reasons.append(_("progress below {0}%").format(risk_progress))
		if flt(kr.confidence) < risk_confidence:
			reasons.append(_("low confidence"))
		if kr.status == "At Risk":
			reasons.append(_("marked At Risk"))
		if kr.end_date and today <= getdate(kr.end_date) <= getdate(near_end) and flt(kr.target_progress) < 90:
			reasons.append(_("end date is near"))
		if reasons:
			key_results_need_attention.append({**kr, "reasons": list(dict.fromkeys(reasons))})

	owners = sorted({item.owner_user for item in objectives if item.get("owner_user")} | {item.assignee for item in key_results if item.get("assignee")})
	owners_without_recent_update = []
	for owner in owners:
		latest = frappe.get_all(
			"OKR Check In",
			filters={"reported_by": owner},
			fields=["name", "checkin_date"],
			order_by="checkin_date desc, modified desc",
			limit=1,
		)
		if not latest or not latest[0].checkin_date or getdate(latest[0].checkin_date) < getdate(cutoff):
			owners_without_recent_update.append({"owner": owner, "last_checkin_date": latest[0].checkin_date if latest else None})

	recommended_next_actions = []
	if at_risk_objectives:
		recommended_next_actions.append(_("Review at-risk objectives with owners and agree recovery actions."))
	if key_results_need_attention:
		recommended_next_actions.append(_("Ask owners to update low-confidence or low-progress key results."))
	if owners_without_recent_update:
		recommended_next_actions.append(_("Send check-in reminders to owners without recent updates."))
	if not recommended_next_actions:
		recommended_next_actions.append(_("No urgent OKR management action detected."))

	return {
		"at_risk_objectives": at_risk_objectives[:20],
		"key_results_need_attention": key_results_need_attention[:20],
		"owners_without_recent_update": owners_without_recent_update[:20],
		"recommended_next_actions": recommended_next_actions,
	}
