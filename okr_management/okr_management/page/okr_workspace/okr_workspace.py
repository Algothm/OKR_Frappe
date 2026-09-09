from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, today

from okr_management.hierarchy_visibility import get_hierarchy_visibility_scope
from okr_management.permissions import is_okr_user
from okr_management.utils.periods import add_period_labels


def get_workspace_plan_names() -> list[str]:
	scope = get_hierarchy_visibility_scope()
	filters = {"status": ["!=", "Archived"]}
	if scope["read_all"]:
		return frappe.get_all("OKR Plan", filters=filters, pluck="name")

	plan_names = set(scope["full_plan_names"])
	if scope["visible_objectives"]:
		plan_names.update(
			filter(
				None,
				frappe.get_all(
					"OKR Objective",
					filters={"name": ["in", list(scope["visible_objectives"])]},
					pluck="parent_plan",
				),
			)
		)
	if not plan_names:
		return []
	filters["name"] = ["in", list(plan_names)]
	return frappe.get_all("OKR Plan", filters=filters, pluck="name")


def get_active_plan_names() -> list[str]:
	return frappe.get_all("OKR Plan", filters={"status": "Active"}, pluck="name")


def empty_workspace_response(year, plan, level, owner) -> dict:
	return base_response([], year, plan, level, owner)


@frappe.whitelist()
def get_workspace_data(
	year: str | None = None, plan: str | None = None, level: str | None = None, owner: str | None = "me"
) -> dict:
	workspace_plan_names = get_workspace_plan_names()
	if not workspace_plan_names:
		return empty_workspace_response(year, plan, level, owner)

	filters = {"parent_plan": ["in", workspace_plan_names]}
	scope = get_hierarchy_visibility_scope()
	if not scope["read_all"]:
		filters["name"] = ["in", list(scope["visible_objectives"])]
	if year:
		filters["financial_year"] = year
	if plan:
		filters["parent_plan"] = plan
	if level:
		filters["level"] = level

	owner = "team" if owner == "all" else owner
	owner = owner if owner in {"me", "team"} else "me"
	# Plan-team members (including the Plan Coordinator) have full visibility
	# for their selected plan. Do not narrow that plan back to only objectives
	# personally owned by the current user when the default "My OKRs" chip is on.
	selected_plan_is_managed = bool(plan and plan in scope["full_plan_names"])
	if owner == "me" and not scope["read_all"] and not selected_plan_is_managed:
		my_objectives = set(scope["owned_objectives"])
		my_key_results = set(scope["owned_key_results"])
		direct_action_items = set(scope["direct_action_items"])
		if scope["read_all"]:
			my_objectives.update(
				frappe.get_all("OKR Objective", filters={"owner_user": frappe.session.user}, pluck="name")
			)
			my_objectives.update(
				frappe.get_all("OKR Objective", filters={"owner": frappe.session.user}, pluck="name")
			)
			my_key_results.update(
				frappe.get_all("OKR Key Result", filters={"assignee": frappe.session.user}, pluck="name")
			)
			my_key_results.update(
				frappe.get_all("OKR Key Result", filters={"owner_user": frappe.session.user}, pluck="name")
			)
			employees = frappe.get_all(
				"Employee", filters={"user_id": frappe.session.user, "status": "Active"}, pluck="name"
			)
			if employees:
				direct_action_items.update(
					frappe.get_all(
						"OKR Action Item",
						filters={"assigned_to": ["in", employees]},
						pluck="name",
					)
				)
		if my_key_results:
			my_objectives.update(
				filter(
					None,
					frappe.get_all(
						"OKR Key Result",
						filters={"name": ["in", list(my_key_results)]},
						pluck="objective",
					),
				)
			)
		if direct_action_items:
			direct_krs = set(
				filter(
					None,
					frappe.get_all(
						"OKR Action Item",
						filters={"name": ["in", list(direct_action_items)]},
						pluck="parent_key_result",
					),
				)
			)
			if direct_krs:
				my_objectives.update(
					filter(
						None,
						frappe.get_all(
							"OKR Key Result",
							filters={"name": ["in", list(direct_krs)]},
							pluck="objective",
						),
					)
				)
		filters["name"] = ["in", list(my_objectives)] if my_objectives else ["in", []]
	objectives = frappe.get_all(
		"OKR Objective",
		filters=filters,
		fields=[
			"name",
			"objective_title",
			"parent_plan",
			"level",
			"priority",
			"owner_user",
			"owner",
			"status",
			"progress",
			"start_date",
			"end_date",
			"attachment",
		],
		order_by="priority desc, modified desc",
		limit_page_length=100,
	)
	add_user_full_names(objectives, "owner", "creator_full_name")

	objective_names = [row.name for row in objectives]
	key_results = get_key_results(objective_names)
	if not scope["read_all"]:
		key_results = [row for row in key_results if row.name in scope["visible_key_results"]]
	action_items = get_action_items([row.name for row in key_results])
	if not scope["read_all"]:
		action_items = [row for row in action_items if row.name in scope["visible_action_items"]]
	add_period_labels(key_results, action_items, objectives)
	histories = get_checkin_history([row.name for row in action_items])
	active_plan_names = set(get_active_plan_names())

	kr_config_by_name = {row.name: row for row in key_results}
	actions_by_kr = {}
	for action in action_items:
		action["history"] = histories.get(action.name, [])
		action["has_today_checkin"] = any(
			str(item.get("checkin_date")) == nowdate() for item in action["history"]
		)
		action["can_checkin"] = (
			action.parent_plan in active_plan_names
			and (scope["read_all"] or action.name in scope["checkin_action_items"])
			and action.status in {"Open", "In Progress", "On Hold", "Blocked", "Archived"}
		)
		kr_config = kr_config_by_name.get(action.parent_key_result)
		action["measurement_locked"] = bool(
			kr_config
			and kr_config.get("lock_measurement_fields_for_action_item_assignees") not in (0, "0")
		)
		action["can_edit_measurement"] = action["can_checkin"] and not action["measurement_locked"]
		actions_by_kr.setdefault(action.parent_key_result, []).append(action)

	krs_by_objective = {}
	for kr in key_results:
		kr["action_items"] = actions_by_kr.get(kr.name, [])
		# KR values and progress are already normalized and persisted by the
		# calculation service. Do not aggregate only checked-in actions here:
		# that excluded zero-progress actions and changed e.g. 4 / 2 into 7 / 4.
		kr["completed_action_items"] = sum(
			1
			for item in kr["action_items"]
			if item.status in ("Completed", "Closed") or flt(item.progress or 0) >= 100
		)
		kr["total_action_items"] = len(kr["action_items"])
		kr["total_checkins"] = sum(len(item["history"]) for item in kr["action_items"])
		krs_by_objective.setdefault(kr.objective, []).append(kr)

	hierarchy = []
	for objective in objectives:
		objective["key_results"] = krs_by_objective.get(objective.name, [])
		if (
			scope["read_all"]
			or objective["key_results"]
			or objective.name in scope["owned_objectives"]
			or objective.parent_plan in scope["full_plan_names"]
		):
			hierarchy.append(objective)

	return base_response(hierarchy, year, plan, level, owner)


@frappe.whitelist()
def get_filter_options() -> dict:
	# Every OKR user needs the complete plan list for workspace context. The
	# objective query below remains hierarchy-scoped, so this does not expose
	# objective, key-result, or action-item data from unrelated plans.
	if not is_okr_user():
		return {"plans": [], "default_plan": ""}

	plans = frappe.get_all(
		"OKR Plan",
		filters={"status": ["!=", "Archived"]},
		fields=["name", "plan_name", "financial_year", "status", "planned_activation_date"],
		limit_page_length=100,
	)
	status_rank = {"Active": 0, "Draft": 1, "Archived": 2}
	plans.sort(
		key=lambda row: (
			status_rank.get(row.status, 1),
			-(getdate(row.planned_activation_date).toordinal() if row.planned_activation_date else 0),
			row.plan_name or row.name,
		)
	)
	default_plan = next((row.name for row in plans if row.status == "Active"), plans[0].name if plans else "")
	return {
		"plans": plans,
		"default_plan": default_plan,
	}


@frappe.whitelist()
def save_workspace_checkin(
	action_item: str,
	progress: float | None = None,
	update: str = "",
	blocker: str | None = None,
	dependency: str | None = None,
	attachment: str | None = None,
	status: str | None = None,
	current_value: float | None = None,
	checkin_date: str | None = None,
) -> dict:
	scope = get_hierarchy_visibility_scope()
	if not scope["read_all"] and action_item not in scope["checkin_action_items"]:
		frappe.throw(
			"You are not authorized to submit a Check-In for this Action Item", frappe.PermissionError
		)
	action = frappe.get_doc("OKR Action Item", action_item)
	key_result_config = frappe.db.get_value(
		"OKR Key Result",
		action.parent_key_result,
		["name", "metric_type", "metric_direction", "baseline_value", "current_value", "target_value"],
		as_dict=True,
	)
	is_custom = bool(action.customize_measurement)
	if is_custom:
		metric_type = action.metric_type or "Percentage"
		metric_direction = action.metric_direction or "Increase"
		baseline = flt(action.baseline_value)
		target = flt(action.target_value)
	else:
		metric_type = key_result_config.metric_type or "Percentage"
		metric_direction = key_result_config.metric_direction or "Increase"
		baseline = flt(key_result_config.baseline_value)
		target = flt(key_result_config.target_value)

	actual_value = flt(current_value if current_value is not None else progress)
	if metric_type == "Boolean":
		calculated_progress = 100.0 if actual_value else 0.0
	elif target == baseline:
		calculated_progress = 0.0
	elif metric_direction == "Decrease":
		calculated_progress = ((baseline - actual_value) / (baseline - target)) * 100.0
	else:
		calculated_progress = ((actual_value - baseline) / (target - baseline)) * 100.0
	calculated_progress = min(100.0, max(0.0, calculated_progress))

	if not is_custom:
		frappe.db.set_value("OKR Key Result", key_result_config.name, "current_value", actual_value)
	frappe.db.set_value("OKR Action Item", action.name, "current_value", actual_value)
	doc = frappe.new_doc("OKR Check In")
	doc.action_item = action_item
	doc.current_value = actual_value
	doc.progress = calculated_progress
	doc.achievements = update
	doc.blockers = blocker or ""
	doc.dependency = dependency or ""
	doc.attachment = attachment or ""
	doc.action_status = status or "In Progress"
	if checkin_date:
		from frappe.utils import getdate
		doc.checkin_date = getdate(checkin_date)
	doc.flags.ignore_permissions = True
	doc.save()
	link_uploaded_attachment(doc)
	result = {"name": doc.name, "message": "Check-in saved successfully"}

	action = frappe.get_doc("OKR Action Item", action_item)
	key_result = frappe.db.get_value(
		"OKR Key Result",
		action.parent_key_result,
		[
			"name",
			"key_result_title",
			"objective",
			"parent_plan",
			"end_date",
			"target_progress",
			"target_value",
			"action_item_count",
			"checkin_count",
		],
		as_dict=True,
	)
	objective = None
	if key_result and key_result.objective:
		objective = frappe.db.get_value(
			"OKR Objective",
			key_result.objective,
			["name", "objective_title", "progress"],
			as_dict=True,
		)

	history = get_checkin_history([action_item]).get(action_item, [])
	add_period_labels([key_result] if key_result else [], [action])
	return {
		"name": result.get("name"),
		"message": result.get("message"),
		"checkin": history[0] if history else None,
		"action_item": {
			"name": action.name,
			"action_item_title": action.action_item_title,
			"parent_key_result": action.parent_key_result,
			"parent_plan": action.parent_plan,
			"period_label": action.get("period_label"),
			"owner_user": action.owner_user,
			"status": action.status,
			"priority": action.priority,
			"progress": flt(action.progress),
			"due_date": action.due_date,
			"history": history,
			"has_today_checkin": any(str(item.get("checkin_date")) == nowdate() for item in history),
		},
		"key_result": key_result,
		"objective": objective,
	}


@frappe.whitelist()
def save_action_measurement(
	action_item: str,
	metric_type: str,
	metric_direction: str,
	baseline_value: float,
	target_value: float,
	current_value: float,
) -> dict:
	"""Save Action Item-specific measurement configuration from the workspace."""
	scope = get_hierarchy_visibility_scope()
	if not scope["read_all"] and action_item not in scope["checkin_action_items"]:
		frappe.throw(_("You are not authorized to update measurement for this Action Item."), frappe.PermissionError)

	action = frappe.get_doc("OKR Action Item", action_item)
	if action.status not in {"Open", "In Progress", "On Hold", "Blocked"}:
		frappe.throw(_("Measurement can only be updated for an active Action Item."))

	plan_status = frappe.db.get_value("OKR Plan", action.parent_plan, "status")
	if plan_status != "Active":
		frappe.throw(_("Measurement can only be updated while the parent OKR Plan is Active."))

	locked = frappe.db.get_value(
		"OKR Key Result",
		action.parent_key_result,
		"lock_measurement_fields_for_action_item_assignees",
	)
	if locked not in (0, "0", None):
		frappe.throw(_("Measurement customization is locked by the Key Result owner."), frappe.PermissionError)

	if metric_type not in {"Percentage", "Number", "Currency", "Boolean"}:
		frappe.throw(_("Invalid Measurement Type."))
	if metric_direction not in {"Increase", "Decrease"}:
		frappe.throw(_("Invalid Goal Direction."))

	baseline = flt(baseline_value)
	target = flt(target_value)
	current = flt(current_value)
	if metric_type == "Boolean":
		baseline, target = 0.0, 1.0
		current = 1.0 if current else 0.0
	else:
		lower, upper = sorted((baseline, target))
		if not lower <= current <= upper:
			frappe.throw(_("Current Value must be between {0} and {1}.").format(lower, upper))

	action.customize_measurement = 1
	action.metric_type = metric_type
	action.metric_direction = metric_direction
	action.baseline_value = baseline
	action.target_value = target
	action.current_value = current
	action.flags.ignore_permissions = True
	action.save()

	return {
		"name": action.name,
		"metric_type": action.metric_type,
		"metric_direction": action.metric_direction,
		"baseline_value": flt(action.baseline_value),
		"target_value": flt(action.target_value),
		"current_value": flt(action.current_value),
		"progress": flt(action.progress),
	}


def base_response(objectives, year, plan, level, owner) -> dict:
	return {
		"today": today(),
		"filters": {"year": year, "plan": plan, "level": level, "owner": owner or "me"},
		"objectives": objectives,
	}


def add_user_full_names(rows: list, source_field: str, target_field: str) -> list:
	user_ids = {row.get(source_field) for row in rows if row.get(source_field)}
	full_names = (
		{
			row.name: row.full_name or row.name
			for row in frappe.get_all(
				"User", filters={"name": ["in", list(user_ids)]}, fields=["name", "full_name"]
			)
		}
		if user_ids
		else {}
	)
	for row in rows:
		user_id = row.get(source_field)
		row[target_field] = full_names.get(user_id, user_id or "")
	return rows


def get_key_results(objective_names: list[str]) -> list:
	if not objective_names:
		return []
	rows = frappe.get_all(
		"OKR Key Result",
		filters={"objective": ["in", objective_names]},
		fields=[
			"name",
			"key_result_title",
			"objective",
			"parent_plan",
			"owner_user",
			"assignee",
			"status",
			"priority",
			"target_progress",
			"metric_type",
			"metric_direction",
			"unit_of_measure",
			"target_value",
			"current_value",
			"baseline_value",
			"currency",
			"action_item_count",
			"checkin_count",
			"lock_measurement_fields_for_action_item_assignees",
			"end_date",
		],
		order_by="priority desc, modified desc",
		limit_page_length=300,
	)
	return add_user_full_names(rows, "assignee", "assignee_full_name")


def get_action_items(kr_names: list[str]) -> list:
	if not kr_names:
		return []
	rows = frappe.get_all(
		"OKR Action Item",
		filters={"parent_key_result": ["in", kr_names]},
		fields=[
			"name",
			"action_item_title",
			"parent_key_result",
			"parent_plan",
			"owner_user",
			"status",
			"priority",
			"progress",
			"due_date",
			"customize_measurement",
			"metric_type",
			"metric_direction",
			"baseline_value",
			"target_value",
			"current_value",
			"attachment",
		],
		order_by="due_date asc, modified desc",
		limit_page_length=800,
	)
	for row in rows:
		if row.get("customize_measurement"):
			row["progress"] = calculate_effective_action_progress(row)
	return add_user_full_names(rows, "owner_user", "owner_full_name")


def link_uploaded_attachment(checkin) -> None:
	"""Attach a Workspace upload so authorized hierarchy viewers can preview private files."""
	if not checkin.attachment:
		return
	file_row = frappe.db.get_value(
		"File",
		{"file_url": checkin.attachment},
		["name", "owner", "attached_to_doctype", "attached_to_name"],
		as_dict=True,
	)
	if not file_row:
		frappe.throw("The selected attachment could not be found.")
	if frappe.session.user != "Administrator" and file_row.owner != frappe.session.user:
		frappe.throw("You can only attach files that you uploaded.", frappe.PermissionError)
	if file_row.attached_to_name and (
		file_row.attached_to_doctype != "OKR Check In" or file_row.attached_to_name != checkin.name
	):
		frappe.throw("This file is already attached to another document.")
	frappe.db.set_value(
		"File",
		file_row.name,
		{"attached_to_doctype": "OKR Check In", "attached_to_name": checkin.name},
		update_modified=False,
	)


def get_checkin_history(action_item_names: list[str]) -> dict:
	if not action_item_names:
		return {}
	rows = frappe.get_all(
		"OKR Check In",
		filters={"action_item": ["in", action_item_names], "status": "Submitted"},
		fields=[
			"action_item",
			"name",
			"checkin_date",
			"progress",
			"current_value",
			"action_status",
			"achievements",
			"blockers",
			"reported_by",
			"attachment",
		],
		order_by="checkin_date desc, creation desc",
		limit_page_length=2000,
	)
	action_assignees = {
		row.name: row.assigned_to
		for row in frappe.get_all(
			"OKR Action Item",
			filters={"name": ["in", action_item_names]},
			fields=["name", "assigned_to"],
		)
	}
	reporters = {row.reported_by for row in rows if row.reported_by}
	reporter_names = (
		{
			row.name: row.full_name or row.name
			for row in frappe.get_all(
				"User", filters={"name": ["in", list(reporters)]}, fields=["name", "full_name"]
			)
		}
		if reporters
		else {}
	)
	out = {}
	for row in rows:
		assignee = action_assignees.get(row.action_item)
		row["delegated_by_name"] = (
			reporter_names.get(row.reported_by, row.reported_by or "")
			if row.reported_by and row.reported_by != assignee
			else ""
		)
		out.setdefault(row.action_item, []).append(row)
	return out


def calculate_effective_action_progress(item: dict) -> float:
	actual = flt(item.get("current_value"))
	baseline = flt(item.get("baseline_value"))
	target = flt(item.get("target_value"))
	m_type = item.get("metric_type") or "Percentage"
	direction = item.get("metric_direction") or "Increase"
	if m_type == "Boolean":
		return 100.0 if actual else 0.0
	if target == baseline:
		return 0.0
	if direction == "Decrease":
		prog = ((baseline - actual) / (baseline - target)) * 100.0
	else:
		prog = ((actual - baseline) / (target - baseline)) * 100.0
	return min(100.0, max(0.0, round(prog, 2)))
