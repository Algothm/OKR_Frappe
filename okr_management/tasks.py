from __future__ import annotations

import frappe


def daily() -> None:
	activate_due_plans()
	publish_due_checkins()


def activate_due_plans(as_of_date=None) -> list[str]:
	"""Activate due Draft Plans and their executable hierarchy; safe to rerun."""
	from frappe.utils import getdate, today

	as_of_date = getdate(as_of_date or today())
	plan_names = frappe.get_all(
		"OKR Plan",
		filters={
			"status": "Draft",
			"planned_activation_date": ["<=", as_of_date],
		},
		pluck="name",
	)
	activated = []
	for index, plan_name in enumerate(plan_names):
		savepoint = f"activate_okr_plan_{index}"
		frappe.db.savepoint(savepoint)
		try:
			if activate_plan(plan_name, as_of_date):
				activated.append(plan_name)
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			frappe.log_error(frappe.get_traceback(), f"Automatic OKR Plan activation failed: {plan_name}")
	return activated


def activate_plan(plan_name: str, as_of_date=None) -> bool:
	from frappe.utils import getdate, today

	plan = frappe.get_doc("OKR Plan", plan_name)
	as_of_date = getdate(as_of_date or today())
	if plan.status != "Draft" or not plan.planned_activation_date:
		return False
	if getdate(plan.planned_activation_date) > as_of_date:
		return False

	plan.status = "Active"
	plan.flags.ignore_permissions = True
	plan.save()
	frappe.db.set_value(
		"OKR Objective",
		{"parent_plan": plan.name, "status": "Draft"},
		"status",
		"Active",
		update_modified=True,
	)
	frappe.db.set_value(
		"OKR Key Result",
		{"parent_plan": plan.name, "status": ["in", ["Draft", "Planned"]]},
		"status",
		"Active",
		update_modified=True,
	)
	return True


def hourly() -> None:
	publish_at_risk_updates()


def publish_due_checkins() -> None:
	checkins = frappe.get_all("OKR Check In", filters={"status": ["=", "Draft"]}, pluck="name")
	for checkin in checkins:
		frappe.publish_realtime("okr_checkin_due", {"checkin": checkin})


def publish_at_risk_updates() -> None:
	items = frappe.get_all("OKR Key Result", filters={"status": "Active", "target_progress": ["<", 60]}, pluck="name")
	for item in items:
		frappe.publish_realtime("okr_key_result_at_risk", {"key_result": item})
