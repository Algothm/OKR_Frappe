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


def calculate_metric_progress(baseline_value: Any, current_value: Any, target_value: Any, metric_direction: str = "Increase", metric_type: str | None = None) -> float:
	"""Return normalized progress; numeric zero is always a real value."""
	baseline = flt(baseline_value)
	current = flt(current_value)
	target = flt(target_value)
	if metric_type == "Boolean":
		return 100.0 if current else 0.0
	if target == baseline:
		return 0.0
	if metric_direction == "Decrease":
		progress = ((baseline - current) / (baseline - target)) * 100.0
	else:
		progress = ((current - baseline) / (target - baseline)) * 100.0
	return round(min(100.0, max(0.0, progress)), 2)


def get_progress_from_values(baseline_value: Any, current_value: Any, target_value: Any) -> float:
	return calculate_metric_progress(baseline_value, current_value, target_value)


def get_current_value_from_progress(baseline_value: Any, target_value: Any, progress_percent: Any) -> float:
	baseline = flt(baseline_value)
	target = flt(target_value)
	return round(baseline + ((target - baseline) * flt(progress_percent) / 100.0), 2)


def get_metric_progress(key_result: Any) -> float:
	if not key_result:
		return 0.0
	return calculate_metric_progress(
		key_result.get('baseline_value'),
		key_result.get('current_value'),
		key_result.get('target_value'),
		key_result.get('metric_direction') or 'Increase',
		key_result.get('metric_type'),
	)


def calculate_action_item_progress(action_item: Any, key_result: Any = None) -> float:
	# Editing permission and calculation source are independent. Once an Action
	# has stored measurement fields, always calculate from those fields even when
	# assignee editing is disabled; fall back to KR only for truly legacy/missing data.
	has_action_metric = bool(action_item.get('metric_type')) and action_item.get('target_value') is not None
	metric = action_item if has_action_metric or not key_result else key_result
	if metric.get('metric_type') == 'Percentage':
		return round(min(100.0, max(0.0, flt(action_item.get('current_value')))), 2)
	return calculate_metric_progress(metric.get('baseline_value'), action_item.get('current_value'), metric.get('target_value'), metric.get('metric_direction') or 'Increase', metric.get('metric_type'))


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
	action_item_count = frappe.db.count('OKR Action Item', {'parent_key_result': key_result_name})
	values: dict[str, Any] = {}
	set_if_has(values, 'OKR Key Result', 'target_progress', progress)
	set_if_has(values, 'OKR Key Result', 'score', progress)
	if action_item_count:
		if key_result.get('metric_type') == 'Boolean':
			current_value = 1.0 if progress >= 100 else 0.0
		else:
			current_value = get_current_value_from_progress(
				key_result.get('baseline_value'),
				key_result.get('target_value'),
				progress,
			)
		set_if_has(values, 'OKR Key Result', 'current_value', current_value)

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
	# Whenever included Action Items exist, their normalized completion average
	# determines KR progress, regardless of the legacy calculation_mode value.
	action_items = frappe.get_all(
		'OKR Action Item',
		filters={'parent_key_result': key_result_name, 'status': ['not in', ['Archived', 'Done']]},
		fields=['name', 'progress', 'current_value', 'customize_measurement', 'metric_type', 'metric_direction', 'baseline_value', 'target_value'],
	)
	if action_items:
		progress_values = []
		for item in action_items:
			latest = frappe.db.get_value(
				'OKR Check In',
				{'action_item': item.get('name')},
				['current_value', 'progress'],
				as_dict=True,
				order_by='checkin_date desc, creation desc',
			)
			if latest:
				# A submitted Check-In is the authoritative Action snapshot.
				current = flt(latest.get('current_value'))
				progress = flt(latest.get('progress'))
			else:
				current = flt(item.get('current_value'))
				progress = calculate_action_item_progress(item, key_result)
			progress_values.append(progress)
			updates = {}
			if flt(item.get('current_value')) != current:
				updates['current_value'] = current
			if flt(item.get('progress')) != progress:
				updates['progress'] = progress
			if updates:
				frappe.db.set_value('OKR Action Item', item.name, updates, update_modified=False)
		return average(progress_values)

	# Without Action Items, fall back to the KR's own configured measurement.
	return get_metric_progress(key_result)


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
	set_if_has(values, 'OKR Plan', 'objective_count', len(objectives))
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

