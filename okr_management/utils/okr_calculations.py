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
		['calculation_mode', 'metric_type', 'metric_direction', 'baseline_value', 'current_value', 'target_value', 'milestone_status'],
		as_dict=True,
	)
	progress = get_key_result_progress(key_result_name, key_result)
	values: dict[str, Any] = {}
	set_if_has(values, 'OKR Key Result', 'target_progress', progress)
	set_if_has(values, 'OKR Key Result', 'score', progress)
	if values:
		frappe.db.set_value('OKR Key Result', key_result_name, values, update_modified=False)
	recalculate_from_key_result(key_result_name)


def get_key_result_progress(key_result_name: str, key_result: Any) -> float:
	if key_result and key_result.get('calculation_mode') == 'Action Item Based':
		action_items = frappe.get_all(
			'OKR Action Item',
			filters={'parenttype': 'OKR Key Result', 'parent': key_result_name, 'status': ['!=', 'Cancelled']},
			fields=['progress', 'weight'],
		)
		if not action_items:
			return 0.0
		if any(flt(item.get('weight')) > 0 for item in action_items):
			total_weighted_progress = sum(flt(item.get('progress')) * flt(item.get('weight')) for item in action_items)
			return round(total_weighted_progress / 100.0, 2)
		return average([item.get('progress') for item in action_items])

	if key_result and key_result.get('metric_type') == 'Boolean':
		return 100.0 if flt(key_result.get('current_value')) else 0.0

	if key_result and key_result.get('metric_type') == 'Milestone':
		return {'Not Started': 0.0, 'In Progress': 50.0, 'Completed': 100.0}.get(
			key_result.get('milestone_status') or 'Not Started',
			0.0,
		)

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
	_recalculate_sprint_for_objective(objective_name)


def _recalculate_sprint_for_objective(objective_name: str) -> None:
	sprint = frappe.db.get_value('OKR Objective', objective_name, 'sprint')
	if sprint:
		recalculate_sprint_progress(sprint)


def recalculate_sprint_progress(sprint_name: str | None) -> None:
	if not sprint_name or not frappe.db.exists('OKR Sprint', sprint_name):
		return

	objectives = frappe.get_all('OKR Objective', filters={'sprint': sprint_name}, fields=['name', 'progress'])
	progress = average([item.get('progress') for item in objectives])
	values: dict[str, Any] = {}
	set_if_has(values, 'OKR Sprint', 'progress', progress)
	set_if_has(values, 'OKR Sprint', 'objective_count', len(objectives))
	if values:
		frappe.db.set_value('OKR Sprint', sprint_name, values, update_modified=False)

	parent_plan = frappe.db.get_value('OKR Sprint', sprint_name, 'parent_plan')
	if parent_plan:
		recalculate_plan_progress(parent_plan)


def recalculate_plan_progress(plan_name: str | None) -> None:
	if not plan_name or not frappe.db.exists('OKR Plan', plan_name):
		return

	sprints = frappe.get_all('OKR Sprint', filters={'parent_plan': plan_name}, fields=['name', 'progress'])
	progress = average([item.get('progress') for item in sprints])
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
	recalculate_sprint_progress(safe_get(doc, 'sprint'))


def sync_checkin_progress(doc: Any, method: str | None = None) -> None:
	key_result_name = safe_get(doc, 'key_result')
	if not key_result_name or not frappe.db.exists('OKR Key Result', key_result_name):
		return

	calculation_mode = frappe.db.get_value('OKR Key Result', key_result_name, 'calculation_mode')
	if calculation_mode != 'Check-in Based':
		return

	values: dict[str, Any] = {}
	progress = flt(safe_get(doc, 'progress', 0))
	set_if_has(values, 'OKR Key Result', 'current_value', flt(safe_get(doc, 'current_value', 0)))
	set_if_has(values, 'OKR Key Result', 'target_progress', progress)
	set_if_has(values, 'OKR Key Result', 'score', progress)
	if values:
		frappe.db.set_value('OKR Key Result', key_result_name, values, update_modified=False)
	recalculate_from_key_result(key_result_name)
