from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, formatdate, nowdate

from okr_management.hierarchy_visibility import get_hierarchy_visibility_scope
from okr_management.permissions import is_okr_admin
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link

ACTIVE_ACTION_STATUSES = ("Open", "In Progress", "On Hold", "Blocked", "Archived")
ACTION_STATUS_MAP = {
	"In Progress": "In Progress",
	"On Hold": "On Hold",
	"Blocked": "Blocked",
	"Archived": "Archived",
}


class OKRCheckIn(Document):
	def before_validate(self) -> None:
		self.reported_by = frappe.session.user
		self.checkin_date = self.checkin_date or nowdate()
		self.status = "Submitted"
		if self.action_item:
			self.populate_from_action_item()
			self.set_metric_progress()
		else:
			self.progress = min(100.0, max(0.0, flt(self.progress)))
			self.progress_percent = self.progress

	def set_metric_progress(self) -> None:
		ai_data = frappe.db.get_value(
			"OKR Action Item",
			self.action_item,
			["customize_measurement", "metric_type", "metric_direction", "baseline_value", "target_value"],
			as_dict=True,
		) if self.action_item else None

		if ai_data and ai_data.customize_measurement:
			metric_type = ai_data.metric_type or "Percentage"
			metric_direction = ai_data.metric_direction or "Increase"
			baseline = flt(ai_data.baseline_value)
			target = flt(ai_data.target_value)
		else:
			key_result = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				["metric_type", "metric_direction", "baseline_value", "target_value"],
				as_dict=True,
			)
			if not key_result:
				frappe.throw(_("The selected Action Item has no valid Key Result."))
			metric_type = key_result.metric_type
			metric_direction = key_result.metric_direction
			baseline = flt(key_result.baseline_value)
			target = flt(key_result.target_value)

		actual = flt(self.current_value)
		if metric_type == "Boolean":
			if actual not in (0, 1):
				frappe.throw(_("Current Value must be 0 or 1 for a Boolean Key Result."))
			progress = 100.0 if actual else 0.0
		else:
			if target == baseline:
				progress = 0.0
			elif metric_direction == "Decrease":
				progress = ((baseline - actual) / (baseline - target)) * 100.0
			else:
				progress = ((actual - baseline) / (target - baseline)) * 100.0

		self.progress = min(100.0, max(0.0, progress))
		self.progress_percent = self.progress

	def validate(self) -> None:
		ensure_required_link(self.action_item, "Action Item")
		ensure_required_link(self.key_result, "Key Result")
		ensure_percentage(self.progress, "Progress")
		ensure_required_link(self.action_status, "Status")

		if self.action_status not in ACTION_STATUS_MAP:
			frappe.throw(_("Please select a valid Status."))

		self.validate_action_item_assignment()
		self.validate_parent_plan_active()

		if self.name and frappe.db.exists("OKR Check In", self.name):
			previous_status = frappe.db.get_value("OKR Check In", self.name, "status")
			if previous_status == "Submitted":
				frappe.throw(_("Submitted Check-ins are read-only and cannot be modified."))

	def populate_from_action_item(self) -> None:
		if not frappe.db.exists("OKR Action Item", self.action_item):
			frappe.throw(_("Selected Action Item does not exist."))

		action = frappe.get_doc("OKR Action Item", self.action_item)
		self.validate_parent_plan_active(action)
		self.validate_action_item_assignment(action)

		key_result = frappe.get_doc("OKR Key Result", action.parent_key_result)
		objective = frappe.get_doc("OKR Objective", key_result.objective)
		parent_plan_name = (
			key_result.parent_plan
			or getattr(action, "parent_plan", None)
			or frappe.db.get_value("OKR Objective", key_result.objective, "parent_plan")
		)
		plan = (
			frappe.get_doc("OKR Plan", parent_plan_name)
			if parent_plan_name and frappe.db.exists("OKR Plan", parent_plan_name)
			else None
		)

		start_date, end_date = (None, None)
		day_count = 0
		if plan:
			from okr_management.okr_management.doctype.okr_plan.okr_plan import get_plan_timeline

			start_date, end_date = get_plan_timeline(plan)
			day_count = date_diff(end_date, start_date) + 1

		self.key_result = key_result.name
		self.objective = objective.name
		self.parent_plan = plan.name if plan else getattr(action, "parent_plan", None)
		self.financial_year = plan.financial_year if plan else getattr(action, "financial_year", None)
		self.company = plan.company if plan else getattr(action, "company", None)
		self.group = objective.group
		self.department = getattr(action, "department", None)

		if not self.action_status:
			self.action_status = "In Progress" if action.status == "Open" else action.status

		self.action_item_title_context = action.action_item_title
		metric_unit = (
			key_result.currency if key_result.metric_type == "Currency" else key_result.unit_of_measure
		)
		unit_suffix = f" {metric_unit}" if metric_unit else ""
		self.progress_overview_context = _("Current Progress: {0}{1} | Target: {2}{1}").format(
			flt(key_result.current_value, 2), unit_suffix, flt(key_result.target_value, 2)
		)
		self.key_result_name_context = key_result.key_result_title
		self.key_result_description_context = key_result.description
		self.objective_name_context = objective.objective_title
		self.objective_description_context = objective.description
		self.plan_name_context = plan.plan_name if plan else ""
		self.plan_description_context = plan.description if plan else ""
		self.organization_context = plan.company if plan else getattr(action, "company", "")
		self.financial_year_context = plan.financial_year if plan else getattr(action, "financial_year", "")
		if action.start_date and action.due_date:
			days = (getdate(action.due_date) - getdate(action.start_date)).days + 1
			self.timeline_preview_context = _("{0} → {1} • {2} Days").format(
				formatdate(action.start_date), formatdate(action.due_date), days
			)
		elif action.due_date:
			self.timeline_preview_context = _("Due Date: {0}").format(formatdate(action.due_date))
		elif key_result.start_date and key_result.end_date:
			days = (getdate(key_result.end_date) - getdate(key_result.start_date)).days + 1
			self.timeline_preview_context = _("{0} → {1} • {2} Days").format(
				formatdate(key_result.start_date), formatdate(key_result.end_date), days
			)
		elif plan and getattr(plan, "start_date", None) and getattr(plan, "end_date", None):
			days = (getdate(plan.end_date) - getdate(plan.start_date)).days + 1
			self.timeline_preview_context = _("Plan: {0} → {1} • {2} Days").format(
				formatdate(plan.start_date), formatdate(plan.end_date), days
			)
		else:
			self.timeline_preview_context = ""
		self.assigned_to_context = (
			frappe.db.get_value("Employee", action.assigned_to, "employee_name") or action.assigned_to
		)

	def validate_parent_plan_active(self, action=None) -> None:
		action = action or frappe.get_doc("OKR Action Item", self.action_item)
		plan_name = action.parent_plan or frappe.db.get_value(
			"OKR Key Result", action.parent_key_result, "parent_plan"
		)
		if not plan_name:
			return
		plan_status = frappe.db.get_value("OKR Plan", plan_name, "status")
		if plan_status != "Active":
			frappe.throw(_("Check-Ins are available only when the parent OKR Plan is Active."))

	def validate_action_item_assignment(self, action=None) -> None:
		action = action or frappe.get_doc("OKR Action Item", self.action_item)
		if self.is_new() and action.status not in ACTIVE_ACTION_STATUSES:
			frappe.throw(_("Check-Ins can only be created for active Action Items."))
		scope = get_hierarchy_visibility_scope()
		if scope["read_all"] or action.name in scope["checkin_action_items"]:
			return
		frappe.throw(_("You are not authorized to create a Check-In for this Action Item."))

	def on_trash(self) -> None:
		if self.status == "Submitted":
			frappe.throw(_("Submitted Check-ins cannot be deleted."))

	def on_update(self) -> None:
		ai_custom = 0
		if self.action_item and frappe.db.exists("OKR Action Item", self.action_item):
			action_status = ACTION_STATUS_MAP[self.action_status]
			ai_custom = frappe.db.get_value("OKR Action Item", self.action_item, "customize_measurement") or 0
			frappe.db.set_value(
				"OKR Action Item",
				self.action_item,
				{
					"progress": self.progress,
					"current_value": flt(self.current_value),
					"status": action_status,
					"completion_date": nowdate() if action_status == "Completed" else None,
				},
			)

		if self.key_result:
			if not ai_custom:
				frappe.db.set_value("OKR Key Result", self.key_result, "current_value", flt(self.current_value))
			from okr_management.utils.okr_calculations import recalculate_key_result_progress

			recalculate_key_result_progress(self.key_result)

	def after_insert(self) -> None:
		sync_checkin_latest_flags(self.action_item)

	def after_delete(self) -> None:
		if self.key_result:
			frappe.db.set_value("OKR Key Result", self.key_result, "current_value", flt(self.current_value))
			from okr_management.utils.okr_calculations import recalculate_key_result_progress

			recalculate_key_result_progress(self.key_result)
		sync_checkin_latest_flags(self.action_item)


def sync_checkin_latest_flags(action_item: str | None) -> None:
	if not action_item:
		return

	# Acquire exclusive row lock on the parent Action Item record to serialize concurrent operations
	frappe.db.get_value("OKR Action Item", action_item, "name", for_update=True)

	checkins = frappe.get_all(
		"OKR Check In",
		filters={"action_item": action_item},
		fields=["name", "is_latest"],
		order_by="checkin_date desc, creation desc",
	)
	if not checkins:
		return

	latest_name = checkins[0].name
	frappe.db.set_value("OKR Check In", latest_name, "is_latest", 1, update_modified=False)

	other_names = [c.name for c in checkins[1:]]
	if other_names:
		frappe.db.set_value(
			"OKR Check In", {"name": ["in", other_names]}, "is_latest", 0, update_modified=False
		)


def rebuild_all_checkin_latest_flags() -> None:
	action_items = frappe.get_all("OKR Check In", pluck="action_item", distinct=True)
	for action_item in action_items:
		sync_checkin_latest_flags(action_item)


def get_logged_in_employees(required: bool = True) -> set[str]:
	employees = set(
		frappe.get_all(
			"Employee",
			filters={"user_id": frappe.session.user, "status": "Active"},
			pluck="name",
		)
	)
	if not employees and required:
		frappe.throw(_("Your user account is not linked to an active Employee."))
	return employees


def get_logged_in_employee(required: bool = True) -> str | None:
	employees = sorted(get_logged_in_employees(required=required))
	return employees[0] if employees else None


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_assigned_action_items(doctype, txt, searchfield, start, page_len, filters):
	user = frappe.session.user
	employees = get_logged_in_employees(required=False)
	roles = frappe.get_roles(user)
	has_broad_access = user == "Administrator" or "OKR Admin" in roles or "System Manager" in roles
	params = {
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}
	if has_broad_access:
		assignment_condition = ""
	else:
		conds = ["ai.owner_user = %(user)s", "ai.owner = %(user)s", "ai.assigned_to = %(user)s"]
		params["user"] = user
		if employees:
			conds.append("ai.assigned_to in %(employees)s")
			params["employees"] = tuple(sorted(employees))
		assignment_condition = "and (" + " or ".join(conds) + ")"
	query = (
		"select ai.name, ai.action_item_title "
		"from `tabOKR Action Item` ai "
		"left join `tabOKR Key Result` kr on kr.name = ai.parent_key_result "
		"left join `tabOKR Plan` plan on plan.name = coalesce(ai.parent_plan, kr.parent_plan) "
		"where ai.status in ('Open', 'In Progress', 'On Hold', 'Blocked', 'Archived') "
		"  and (plan.status in ('Active', 'Draft') or plan.name is null) " + assignment_condition + " "
		"  and (ai.name like %(txt)s or ai.action_item_title like %(txt)s) "
		"order by ai.modified desc "
		"limit %(start)s, %(page_len)s"
	)
	return frappe.db.sql(query, params)


@frappe.whitelist()
def get_action_item_context(action_item: str) -> dict:
	doc = frappe.new_doc("OKR Check In")
	doc.action_item = action_item
	doc.populate_from_action_item()

	ai_data = frappe.db.get_value(
		"OKR Action Item",
		action_item,
		[
			"customize_measurement",
			"metric_type",
			"metric_direction",
			"baseline_value",
			"target_value",
			"current_value",
			"progress",
		],
		as_dict=True,
	)

	if ai_data and ai_data.customize_measurement:
		metric = frappe._dict({
			"metric_type": ai_data.metric_type or "Percentage",
			"metric_direction": ai_data.metric_direction or "Increase",
			"baseline_value": flt(ai_data.baseline_value),
			"target_value": flt(ai_data.target_value),
			"current_value": flt(ai_data.current_value),
			"currency": "",
			"unit_of_measure": "",
			"target_progress": flt(ai_data.progress),
		})
	else:
		metric = frappe.db.get_value(
			"OKR Key Result",
			doc.key_result,
			[
				"metric_type",
				"metric_direction",
				"baseline_value",
				"current_value",
				"target_value",
				"currency",
				"unit_of_measure",
				"target_progress",
			],
			as_dict=True,
		)

	doc.current_value = (
		metric.get("current_value") if metric.get("current_value") is not None else (metric.get("baseline_value") or 0)
	)
	doc.progress = metric.get("target_progress") or 0
	result = {
		fieldname: doc.get(fieldname)
		for fieldname in (
			"current_value",
			"progress",
			"key_result",
			"objective",
			"parent_plan",
			"financial_year",
			"company",
			"group",
			"department",
			"action_status",
			"action_item_title_context",
			"progress_overview_context",
			"key_result_name_context",
			"key_result_description_context",
			"objective_name_context",
			"objective_description_context",
			"plan_name_context",
			"plan_description_context",
			"organization_context",
			"financial_year_context",
			"timeline_preview_context",
			"assigned_to_context",
		)
	}
	result["metric"] = metric
	return result
