from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, nowdate


def has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def safe_get(doc: Any, fieldname: str, default: Any = None) -> Any:
	return doc.get(fieldname) if hasattr(doc, "get") and has_field(doc.doctype, fieldname) else default


def set_if_has(values: dict[str, Any], doctype: str, fieldname: str, value: Any) -> None:
	if has_field(doctype, fieldname):
		values[fieldname] = value


def get_completion_percentage(current_value: Any, target_value: Any) -> float:
	target = flt(target_value)
	if target <= 0:
		return 0.0
	return min(100.0, max(0.0, (flt(current_value) / target) * 100.0))


def get_progress_from_values(baseline_value: Any, current_value: Any, target_value: Any) -> float:
	baseline = flt(baseline_value)
	target = flt(target_value)
	if target == baseline:
		return 0.0
	progress = ((flt(current_value) - baseline) / (target - baseline)) * 100.0
	return min(100.0, max(0.0, progress))


def get_current_value_from_progress(baseline_value: Any, target_value: Any, progress_percent: Any) -> float:
	baseline = flt(baseline_value)
	target = flt(target_value)
	return round(baseline + ((target - baseline) * flt(progress_percent) / 100.0), 2)


def get_latest_checkin(key_result_name: str) -> dict[str, Any] | None:
	fields = ["name", "checkin_date", "progress", "manager_feedback", "review_status", "reported_by", "confidence", "has_dependency", "impact_level"]
	fields = [field for field in fields if has_field("OKR Check In", field)]
	checkin = frappe.get_all(
		"OKR Check In",
		filters={"key_result": key_result_name},
		fields=fields,
		order_by="checkin_date desc, modified desc",
		limit=1,
	)
	return checkin[0] if checkin else None


def sync_checkin_progress(doc: Any, method: str | None = None) -> None:
	key_result_name = safe_get(doc, "key_result")
	if not key_result_name or not frappe.db.exists("OKR Key Result", key_result_name):
		return

	key_result = frappe.get_doc("OKR Key Result", key_result_name)
	progress = flt(safe_get(doc, "progress", 0))

	if has_field("OKR Key Result", "current_value"):
		key_result.current_value = flt(safe_get(doc, "current_value", 0))
	if has_field("OKR Key Result", "target_progress"):
		key_result.target_progress = progress
	if has_field("OKR Key Result", "confidence") and safe_get(doc, "confidence"):
		key_result.confidence = safe_get(doc, "confidence")
	if has_field("OKR Key Result", "last_checkin_date"):
		key_result.last_checkin_date = safe_get(doc, "checkin_date") or nowdate()
	if has_field("OKR Key Result", "last_checkin"):
		key_result.last_checkin = doc.name

	# Flexible Status Calculation:
	# Blocked if review_status is Blocked or dependency impact is Critical
	# At Risk if review_status is Escalated/Needs Improvement, confidence is 1/2, or dependency impact is High
	if has_field("OKR Key Result", "status"):
		review_status = safe_get(doc, "review_status")
		has_dep = bool(safe_get(doc, "has_dependency"))
		impact = safe_get(doc, "impact_level")
		confidence = safe_get(doc, "confidence")

		if review_status == "Blocked" or (has_dep and impact == "Critical"):
			key_result.status = "Blocked"
		elif review_status in ("Escalated", "Needs Improvement") or confidence in ("1", "2") or (has_dep and impact == "High"):
			key_result.status = "At Risk"
		elif progress >= 100:
			key_result.status = "Achieved"
		else:
			key_result.status = "Active"

	key_result.flags.ignore_permissions = True
	key_result.save()


def recalculate_objective_progress(objective_name: str | None) -> None:
	if not objective_name or not frappe.db.exists("OKR Objective", objective_name):
		return

	fields = ["name"]
	for field in ("target_progress", "weight", "status", "confidence"):
		if has_field("OKR Key Result", field):
			fields.append(field)
	key_results = frappe.get_all("OKR Key Result", filters={"objective": objective_name}, fields=fields)

	values: dict[str, Any] = {}
	if not key_results:
		set_if_has(values, "OKR Objective", "progress", 0)
		set_if_has(values, "OKR Objective", "status", "Draft")
		if values:
			frappe.db.set_value("OKR Objective", objective_name, values, update_modified=False)
		_recalculate_cycle_for_objective(objective_name)
		return

	total_weight = sum(flt(item.get("weight")) for item in key_results) or len(key_results)
	weighted_progress = 0.0
	confidence_total = 0.0
	confidence_count = 0
	has_blocked_kr = False
	has_at_risk_kr = False

	for item in key_results:
		weight = flt(item.get("weight")) or 1.0
		weighted_progress += flt(item.get("target_progress")) * weight
		if item.get("confidence") is not None:
			confidence_total += flt(item.get("confidence"))
			confidence_count += 1
		if item.get("status") == "Blocked":
			has_blocked_kr = True
		elif item.get("status") == "At Risk":
			has_at_risk_kr = True

	progress = round(weighted_progress / total_weight, 2)
	confidence = round(confidence_total / confidence_count, 2) if confidence_count else 0
	
	status = "Active"
	if progress >= 100:
		status = "Completed"
	elif has_blocked_kr or has_at_risk_kr or progress < 60:
		status = "At Risk"

	set_if_has(values, "OKR Objective", "progress", progress)
	set_if_has(values, "OKR Objective", "confidence", confidence)
	set_if_has(values, "OKR Objective", "status", status)
	if values:
		frappe.db.set_value("OKR Objective", objective_name, values, update_modified=False)
	_recalculate_cycle_for_objective(objective_name)


def _recalculate_cycle_for_objective(objective_name: str) -> None:
	if has_field("OKR Objective", "cycle"):
		cycle = frappe.db.get_value("OKR Objective", objective_name, "cycle")
		if cycle:
			recalculate_cycle_progress(cycle)


def recalculate_cycle_progress(cycle_name: str | None) -> None:
	if not cycle_name or not frappe.db.exists("OKR Cycle", cycle_name):
		return

	fields = ["name"]
	for field in ("progress", "status"):
		if has_field("OKR Objective", field):
			fields.append(field)
	objectives = frappe.get_all("OKR Objective", filters={"cycle": cycle_name}, fields=fields)

	values: dict[str, Any] = {}
	if not objectives:
		set_if_has(values, "OKR Cycle", "progress", 0)
		set_if_has(values, "OKR Cycle", "status", "Draft")
	elif has_field("OKR Objective", "progress"):
		progress = round(sum(flt(item.get("progress")) for item in objectives) / len(objectives), 2)
		set_if_has(values, "OKR Cycle", "progress", progress)
		if progress >= 100:
			status = "Closed"
		elif progress >= 60:
			status = "Active"
		else:
			status = "Review in Progress"
		set_if_has(values, "OKR Cycle", "status", status)

	if values:
		frappe.db.set_value("OKR Cycle", cycle_name, values, update_modified=False)


def recalculate_from_key_result(key_result_name: str | None) -> None:
	if not key_result_name or not frappe.db.exists("OKR Key Result", key_result_name):
		return
	objective = frappe.db.get_value("OKR Key Result", key_result_name, "objective")
	recalculate_objective_progress(objective)


def recalculate_from_key_result_doc(doc: Any, method: str | None = None) -> None:
	recalculate_from_key_result(getattr(doc, "name", None))


def recalculate_from_objective_doc(doc: Any, method: str | None = None) -> None:
	if has_field("OKR Objective", "cycle"):
		recalculate_cycle_progress(safe_get(doc, "cycle"))

