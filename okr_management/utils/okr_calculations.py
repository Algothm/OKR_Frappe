from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt


def has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def safe_get(doc: Any, fieldname: str, default: Any = None) -> Any:
	return doc.get(fieldname) if hasattr(doc, 'get') and has_field(doc.doctype, fieldname) else default


def set_if_has(values: dict[str, Any], doctype: str, fieldname: str, value: Any) -> None:
	if has_field(doctype, fieldname):
		values[fieldname] = value


def average(values: list[Any]) -> float:
	if not values:
		return 0.0
	return round(sum(flt(value) for value in values) / len(values), 2)


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


def recalculate_key_result_progress(key_result_name: str | None) -> None:
	if not key_result_name or not frappe.db.exists('OKR Key Result', key_result_name):
		return

	key_result = frappe.db.get_value(
		'OKR Key Result',
		key_result_name,
		['calculation_mode', 'metric_type', 'metric_direction', 'baseline_value', 'current_value', 'target_value'],
		as_dict=True,
	)
	progress = get_key_result_progress(key_result_name, key_result)
	values: dict[str, Any] = {}
	set_if_has(values, 'OKR Key Result', 'target_progress', progress)
	set_if_has(values, 'OKR Key Result', 'score', progress)

	action_item_count = frappe.db.count('OKR Action Item', {'parent_key_result': key_result_name})
	checkin_count = frappe.db.count('OKR Check In', {'key_result': key_result_name})
	set_if_has(values, 'OKR Key Result', 'action_item_count', action_item_count)
	set_if_has(values, 'OKR Key Result', 'checkin_count', checkin_count)


	if values:
		frappe.db.set_value('OKR Key Result', key_result_name, values, update_modified=False)
	recalculate_from_key_result(key_result_name)


def get_key_result_progress(key_result_name: str, key_result: Any) -> float:
	"""Key Result Progress = Average(Action Item Progress).
	When Action Items exist, their average always determines KR progress.
	When no Action Items exist, fall back to metric-based calculation.
	"""
	# Always use average of action items when they exist (regardless of calculation_mode)
	action_items = frappe.get_all(
		'OKR Action Item',
		filters={'parent_key_result': key_result_name, 'status': ['!=', 'Cancelled']},
		fields=['progress'],
	)
	if action_items:
		return average([item.get('progress') for item in action_items])

	# No Action Items: fall back to metric-based calculation
	if key_result and key_result.get('metric_type') == 'Boolean':
		return 100.0 if flt(key_result.get('current_value')) else 0.0

	if key_result and key_result.get('metric_direction') == 'Decrease':
		baseline = flt(key_result.get('baseline_value'))
		target = flt(key_result.get('target_value'))
		if target == baseline:
			return 0.0
		progress = ((baseline - flt(key_result.get('current_value'))) / (baseline - target)) * 100.0
		return round(min(100.0, max(0.0, progress)), 2)

	return get_progress_from_values(
		key_result.get('baseline_value') if key_result else 0,
		key_result.get('current_value') if key_result else 0,
		key_result.get('target_value') if key_result else 0,
	)


def recalculate_objective_progress(objective_name: str | None) -> None:
	if not objective_name or not frappe.db.exists('OKR Objective', objective_name):
		return

	progress_field = 'target_progress' if has_field('OKR Key Result', 'target_progress') else 'progress'
	key_results = frappe.get_all(
		'OKR Key Result',
		filters={'objective': objective_name},
		fields=['name', progress_field],
	)
	progress = average([item.get(progress_field) for item in key_results])
	values: dict[str, Any] = {}
	set_if_has(values, 'OKR Objective', 'progress', progress)
	set_if_has(values, 'OKR Objective', 'key_result_count', len(key_results))
	if values:
		frappe.db.set_value('OKR Objective', objective_name, values, update_modified=False)
	_recalculate_plan_for_objective(objective_name)


def _recalculate_plan_for_objective(objective_name: str) -> None:
	plan = frappe.db.get_value('OKR Objective', objective_name, 'parent_plan')
	if plan:
		recalculate_plan_progress(plan)


def recalculate_plan_progress(plan_name: str | None) -> None:
	if not plan_name or not frappe.db.exists('OKR Plan', plan_name):
		return

	objectives = frappe.get_all('OKR Objective', filters={'parent_plan': plan_name}, fields=['name', 'progress'])
	progress = average([item.get('progress') for item in objectives])
	values: dict[str, Any] = {}
	set_if_has(values, 'OKR Plan', 'progress', progress)
	if values:
		frappe.db.set_value('OKR Plan', plan_name, values, update_modified=False)


def recalculate_from_key_result(key_result_name: str | None) -> None:
	if not key_result_name or not frappe.db.exists('OKR Key Result', key_result_name):
		return
	objective = frappe.db.get_value('OKR Key Result', key_result_name, 'objective')
	recalculate_objective_progress(objective)


def recalculate_from_key_result_doc(doc: Any, method: str | None = None) -> None:
	recalculate_key_result_progress(getattr(doc, 'name', None))


def recalculate_from_objective_doc(doc: Any, method: str | None = None) -> None:
	recalculate_plan_progress(safe_get(doc, 'parent_plan'))
