from __future__ import annotations

import frappe

from okr_management.permissions import is_okr_admin, is_okr_user

EDITABLE_PLAN_TEAM_ROLES = {"Plan Coordinator", "Contributor"}


def _plan_team_plans(user, roles=None):
	filters = {"member_user": user, "parenttype": "OKR Plan"}
	if roles:
		filters["role"] = ["in", sorted(roles)]
	return set(frappe.get_all("OKR Plan Team Member", filters=filters, pluck="parent"))


def get_assigned_action_items(user=None):
	user = user or frappe.session.user
	employee_names = frappe.get_all("Employee", filters={"user_id": user, "status": "Active"}, pluck="name")
	return set(
		frappe.get_all(
			"OKR Action Item",
			filters={"assigned_to": ["in", [user, *employee_names]]},
			pluck="name",
		)
	)


def get_hierarchy_visibility_scope(user=None):
	user = user or frappe.session.user
	if not is_okr_user(user):
		return {
			"visible_objectives": set(),
			"visible_key_results": set(),
			"visible_action_items": set(),
			"owned_objectives": set(),
			"owned_key_results": set(),
			"full_key_results": set(),
			"direct_action_items": set(),
			"assigned_action_items": set(),
			"checkin_action_items": set(),
			"full_plan_names": set(),
			"editable_plan_names": set(),
			"checkin_override": False,
			"read_all": False,
		}

	roles = set(frappe.get_roles(user))
	if user == "Administrator" or bool({"System Manager", "OKR Admin"} & roles):
		return {
			"visible_objectives": set(),
			"visible_key_results": set(),
			"visible_action_items": set(),
			"owned_objectives": set(),
			"owned_key_results": set(),
			"full_key_results": set(),
			"direct_action_items": set(),
			"assigned_action_items": get_assigned_action_items(user),
			"checkin_action_items": set(),
			"full_plan_names": set(),
			"editable_plan_names": set(),
			"checkin_override": False,
			"read_all": True,
		}

	employee_rows = frappe.get_all(
		"Employee",
		filters={"user_id": user, "status": "Active"},
		fields=["name", "department", "company"],
	)
	employees = {row.name for row in employee_rows}
	user_identifiers = {user} | employees

	full_plan_names = _plan_team_plans(user)
	editable_plan_names = _plan_team_plans(user, EDITABLE_PLAN_TEAM_ROLES)
	coordinator_plan_names = _plan_team_plans(user, {"Plan Coordinator", "Admin"})

	# 1. Directly Owned Objectives
	owned_objectives = set(
		frappe.get_all("OKR Objective", filters={"owner_user": ["in", list(user_identifiers)]}, pluck="name")
	)
	owned_objectives.update(
		frappe.get_all("OKR Objective", filters={"owner": ["in", list(user_identifiers)]}, pluck="name")
	)

	# 2. Directly Owned / Assigned Key Results
	owned_krs = set(
		frappe.get_all("OKR Key Result", filters={"assignee": ["in", list(user_identifiers)]}, pluck="name")
	)
	owned_krs.update(
		frappe.get_all("OKR Key Result", filters={"owner_user": ["in", list(user_identifiers)]}, pluck="name")
	)
	owned_krs.update(
		frappe.get_all("OKR Key Result", filters={"owner": ["in", list(user_identifiers)]}, pluck="name")
	)

	# 3. Directly Owned / Assigned Action Items
	assigned_actions = get_assigned_action_items(user)
	direct_actions = set(assigned_actions)
	direct_actions.update(
		frappe.get_all(
			"OKR Action Item", filters={"owner_user": ["in", list(user_identifiers)]}, pluck="name"
		)
	)
	direct_actions.update(
		frappe.get_all("OKR Action Item", filters={"owner": ["in", list(user_identifiers)]}, pluck="name")
	)

	# --- Tree Computation ---
	# Descendants of owned Objectives
	obj_child_krs = (
		set(
			frappe.get_all(
				"OKR Key Result", filters={"objective": ["in", list(owned_objectives)]}, pluck="name"
			)
		)
		if owned_objectives
		else set()
	)

	obj_grandchild_actions = (
		set(
			frappe.get_all(
				"OKR Action Item", filters={"parent_key_result": ["in", list(obj_child_krs)]}, pluck="name"
			)
		)
		if obj_child_krs
		else set()
	)

	# Descendants of owned Key Results
	kr_child_actions = (
		set(
			frappe.get_all(
				"OKR Action Item", filters={"parent_key_result": ["in", list(owned_krs)]}, pluck="name"
			)
		)
		if owned_krs
		else set()
	)

	# Ancestors of owned Key Results
	kr_parent_objs = (
		set(
			filter(
				None,
				frappe.get_all(
					"OKR Key Result", filters={"name": ["in", list(owned_krs)]}, pluck="objective"
				),
			)
		)
		if owned_krs
		else set()
	)

	# Ancestors of direct Action Items
	action_parent_krs = (
		set(
			filter(
				None,
				frappe.get_all(
					"OKR Action Item",
					filters={"name": ["in", list(direct_actions)]},
					pluck="parent_key_result",
				),
			)
		)
		if direct_actions
		else set()
	)

	action_grandparent_objs = (
		set(
			filter(
				None,
				frappe.get_all(
					"OKR Key Result", filters={"name": ["in", list(action_parent_krs)]}, pluck="objective"
				),
			)
		)
		if action_parent_krs
		else set()
	)

	# Plan Team Membership
	plan_objectives = set()
	plan_key_results = set()
	plan_action_items = set()
	if full_plan_names:
		plan_objectives = set(
			frappe.get_all(
				"OKR Objective", filters={"parent_plan": ["in", list(full_plan_names)]}, pluck="name"
			)
		)
		if plan_objectives:
			plan_key_results = set(
				frappe.get_all(
					"OKR Key Result", filters={"objective": ["in", list(plan_objectives)]}, pluck="name"
				)
			)
		if plan_key_results:
			plan_action_items = set(
				frappe.get_all(
					"OKR Action Item",
					filters={"parent_key_result": ["in", list(plan_key_results)]},
					pluck="name",
				)
			)

	coordinator_actions = (
		set(
			frappe.get_all(
				"OKR Action Item",
				filters={"parent_plan": ["in", list(coordinator_plan_names)]},
				pluck="name",
			)
		)
		if coordinator_plan_names
		else set()
	)

	# Combine total visible sets
	visible_objectives = owned_objectives | kr_parent_objs | action_grandparent_objs | plan_objectives
	visible_key_results = owned_krs | obj_child_krs | action_parent_krs | plan_key_results
	visible_action_items = direct_actions | kr_child_actions | obj_grandchild_actions | plan_action_items
	checkin_action_items = direct_actions | kr_child_actions | obj_grandchild_actions | coordinator_actions

	return {
		"visible_objectives": visible_objectives,
		"visible_key_results": visible_key_results,
		"visible_action_items": visible_action_items,
		"owned_objectives": owned_objectives,
		"owned_key_results": owned_krs,
		"full_key_results": owned_krs | obj_child_krs,
		"direct_action_items": direct_actions,
		"assigned_action_items": assigned_actions,
		"checkin_action_items": checkin_action_items,
		"full_plan_names": full_plan_names,
		"editable_plan_names": editable_plan_names,
		"checkin_override": False,
		"read_all": False,
	}


def _condition(doctype, names):
	if not names:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(name) for name in sorted(names))
	return f"`tab{doctype}`.name in ({escaped})"


def _query(scope_key, doctype, user=None):
	scope = get_hierarchy_visibility_scope(user)
	return "" if scope["read_all"] else _condition(doctype, scope[scope_key])


def objective_query(user=None):
	return _query("visible_objectives", "OKR Objective", user)


def key_result_query(user=None):
	return _query("visible_key_results", "OKR Key Result", user)


def action_item_query(user=None):
	return _query("visible_action_items", "OKR Action Item", user)


def checkin_query(user=None):
	scope = get_hierarchy_visibility_scope(user)
	if scope["read_all"]:
		return ""
	names = scope["visible_action_items"]
	if not names:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(name) for name in sorted(names))
	return f"`tabOKR Check In`.action_item in ({escaped})"


def _hierarchy_permission(doc, user, ptype, read_key, write_key):
	scope = get_hierarchy_visibility_scope(user)
	if scope["read_all"]:
		return None
	if not doc:
		return user not in {"Guest", ""}
	doc_name = doc if isinstance(doc, str) else getattr(doc, "name", None)
	if not doc_name:
		return user not in {"Guest", ""}
	if ptype in {"write", "delete", "submit", "cancel", "amend"}:
		return doc_name in scope[write_key]
	return doc_name in scope[read_key]


def objective_permission(doc, user=None, ptype=None):
	user = user or frappe.session.user
	scope = get_hierarchy_visibility_scope(user)
	if ptype == "create" and not scope["read_all"]:
		return user not in {"Guest", ""} and is_okr_user(user)
	return _hierarchy_permission(doc, user, ptype, "visible_objectives", "owned_objectives")


def key_result_permission(doc, user=None, ptype=None):
	user = user or frappe.session.user
	scope = get_hierarchy_visibility_scope(user)
	if ptype == "create" and not scope["read_all"]:
		if not doc:
			return user not in {"Guest", ""}
		objective = getattr(doc, "objective", None)
		if not objective:
			return user not in {"Guest", ""}
		return (
			objective in scope["owned_objectives"]
			or frappe.db.get_value("OKR Objective", objective, "parent_plan") in scope["editable_plan_names"]
		)
	return _hierarchy_permission(doc, user, ptype, "visible_key_results", "owned_key_results")


def action_item_permission(doc, user=None, ptype=None):
	user = user or frappe.session.user
	scope = get_hierarchy_visibility_scope(user)
	if ptype == "create" and not scope["read_all"]:
		if not doc:
			return user not in {"Guest", ""}
		parent_kr = getattr(doc, "parent_key_result", None)
		if not parent_kr:
			return user not in {"Guest", ""}
		parent = frappe.db.get_value("OKR Key Result", parent_kr, ["objective", "parent_plan"], as_dict=True)
		return bool(parent) and (
			parent_kr in scope["owned_key_results"]
			or parent.objective in scope["owned_objectives"]
			or parent.parent_plan in scope["editable_plan_names"]
		)
	return _hierarchy_permission(doc, user, ptype, "visible_action_items", "direct_action_items")


def checkin_permission(doc, user=None, ptype=None):
	user = user or frappe.session.user
	scope = get_hierarchy_visibility_scope(user)
	write_types = {"create", "write", "delete", "submit", "cancel", "amend"}
	if scope["read_all"]:
		return None
	if not doc:
		return user not in {"Guest", ""}

	action_item = getattr(doc, "action_item", None) if not isinstance(doc, str) else None
	if not action_item and isinstance(doc, str):
		action_item = frappe.db.get_value("OKR Check In", doc, "action_item")

	if ptype in {"create", "write"} and not action_item:
		return user not in {"Guest", ""} and is_okr_user(user)

	if ptype in write_types:
		return bool(action_item) and action_item in scope["checkin_action_items"]

	# Viewing (read) a Check-In is allowed for any user in the ancestor hierarchy of that Action Item
	return bool(action_item) and action_item in scope["visible_action_items"]
