from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt


def _row_title(row: dict[str, Any], title_field: str) -> str:
	return row.get(title_field) or row.get("name") or ""


def _safe_get_list(doctype: str, **kwargs) -> list[frappe._dict]:
	if not frappe.db.exists("DocType", doctype):
		return []
	return frappe.get_list(doctype, **kwargs)


@frappe.whitelist()
def get_okr_hierarchy_tree(cycle: str | None = None) -> list[dict[str, Any]]:
	"""Return permission-aware OKR hierarchy: Cycle -> Objective -> Key Result -> Action Item."""
	cycle_filters = {}
	if cycle:
		cycle_filters["name"] = cycle

	cycles = _safe_get_list(
		"OKR Cycle",
		filters=cycle_filters,
		fields=["name", "cycle_name", "company", "status", "start_date", "end_date"],
		order_by="start_date desc, modified desc",
		limit_page_length=200,
	)
	cycle_names = [row.name for row in cycles]
	if not cycle_names:
		return []

	objectives = _safe_get_list(
		"OKR Objective",
		filters={"cycle": ["in", cycle_names]},
		fields=["name", "objective_title", "cycle", "parent_objective", "objective_type", "department", "owner_user", "status", "progress", "confidence"],
		order_by="idx asc, creation asc",
		limit_page_length=1000,
	)
	objective_names = [row.name for row in objectives]

	key_results = _safe_get_list(
		"OKR Key Result",
		filters={"objective": ["in", objective_names]} if objective_names else {"name": "__never__"},
		fields=["name", "key_result_title", "objective", "owner_user", "status", "target_progress", "confidence", "end_date"],
		order_by="idx asc, creation asc",
		limit_page_length=2000,
	)
	kr_names = [row.name for row in key_results]

	action_items = _safe_get_list(
		"OKR Action Item",
		filters={"key_result": ["in", kr_names]} if kr_names else {"name": "__never__"},
		fields=["name", "action_item_title", "key_result", "owner_user", "department", "status", "priority", "due_date"],
		order_by="due_date asc, modified desc",
		limit_page_length=3000,
	)

	actions_by_kr: dict[str, list[dict[str, Any]]] = {}
	for action in action_items:
		actions_by_kr.setdefault(action.key_result, []).append({
			"type": "Action Item",
			"doctype": "OKR Action Item",
			"name": action.name,
			"title": _row_title(action, "action_item_title"),
			"owner": action.owner_user,
			"department": action.department,
			"status": action.status,
			"priority": action.priority,
			"due_date": action.due_date,
		})

	krs_by_objective: dict[str, list[dict[str, Any]]] = {}
	for kr in key_results:
		krs_by_objective.setdefault(kr.objective, []).append({
			"type": "Key Result",
			"doctype": "OKR Key Result",
			"name": kr.name,
			"title": _row_title(kr, "key_result_title"),
			"owner": kr.owner_user,
			"status": kr.status,
			"progress": round(flt(kr.target_progress), 2),
			"confidence": kr.confidence,
			"end_date": kr.end_date,
			"children": actions_by_kr.get(kr.name, []),
		})

	objective_by_name = {row.name: row for row in objectives}
	children_by_parent: dict[str, list[frappe._dict]] = {}
	roots_by_cycle: dict[str, list[frappe._dict]] = {}
	for obj in objectives:
		parent = obj.parent_objective
		if parent and parent in objective_by_name:
			children_by_parent.setdefault(parent, []).append(obj)
		else:
			roots_by_cycle.setdefault(obj.cycle, []).append(obj)

	def objective_node(obj: frappe._dict) -> dict[str, Any]:
		children = [objective_node(child) for child in children_by_parent.get(obj.name, [])]
		children.extend(krs_by_objective.get(obj.name, []))
		return {
			"type": "Objective",
			"doctype": "OKR Objective",
			"name": obj.name,
			"title": _row_title(obj, "objective_title"),
			"objective_type": obj.objective_type,
			"department": obj.department,
			"owner": obj.owner_user,
			"status": obj.status,
			"progress": round(flt(obj.progress), 2),
			"confidence": obj.confidence,
			"children": children,
		}

	result = []
	for cycle_row in cycles:
		result.append({
			"type": "Cycle",
			"doctype": "OKR Cycle",
			"name": cycle_row.name,
			"title": cycle_row.cycle_name or cycle_row.name,
			"company": cycle_row.company,
			"status": cycle_row.status,
			"start_date": cycle_row.start_date,
			"end_date": cycle_row.end_date,
			"children": [objective_node(obj) for obj in roots_by_cycle.get(cycle_row.name, [])],
		})
	return result
