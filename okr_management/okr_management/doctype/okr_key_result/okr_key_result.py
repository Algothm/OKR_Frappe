from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from okr_management.okr_management.doctype.okr_plan.okr_plan import get_derived_periods

VALID_PRIORITIES = {"Low", "Medium", "High"}
VALID_STATUSES = {"Draft", "Planned", "Active", "On Hold", "Completed", "Closed", "Archived"}
VALID_CALCULATION_MODES = {"Manual", "Automatic"}
VALID_MEASUREMENT_TYPES = {"Percentage", "Number", "Currency", "Boolean"}
VALID_MEASUREMENT_DIRECTIONS = {"Increase", "Decrease"}

INHERITED_FIELDS = {
	"parent_plan",
	"objective_title",
	"company",
	"financial_year",
	"group",
	"department",
	"plan_owner",
	"objective_owner",
	"objective_level",
}

# Placeholder values mapping removed


class OKRKeyResult(Document):
	def before_validate(self) -> None:
		if self.lock_measurement_fields_for_action_item_assignees is None:
			self.lock_measurement_fields_for_action_item_assignees = 1


		if self.assignee:
			self.owner_user = self.assignee
		elif self.owner_user:
			self.assignee = self.owner_user
		self.priority = self.priority or "Medium"
		self.status = self.status or "Draft"
		self.calculation_mode = self.calculation_mode or "Manual"
		self.metric_type = self.metric_type or "Percentage"
		self.metric_direction = self.metric_direction or "Increase"

		if self.baseline_value is None:
			self.baseline_value = 0.0

		if self.current_value is None:
			self.current_value = 0.0

		if self.is_new() and self.metric_type == "Percentage" and self.target_value is None:
			self.target_value = 100.0
		elif self.metric_type == "Boolean" and self.target_value not in [0.0, 1.0]:
			self.target_value = 1.0

		if self.metric_type == "Percentage" and not self.unit_of_measure:
			self.unit_of_measure = "%"
		elif self.metric_type in ["Boolean", "Currency"]:
			self.unit_of_measure = None

		if self.metric_type == "Currency" and not self.currency:
			if self.company:
				self.currency = frappe.db.get_value("Company", self.company, "default_currency")
			if not self.currency:
				self.currency = frappe.db.get_default("currency")

		self.inherit_context_from_objective()

		# Calculate count of standalone Action Items and check-ins
		if self.name:
			self.action_item_count = frappe.db.count("OKR Action Item", {"parent_key_result": self.name})
			self.checkin_count = frappe.db.count("OKR Check In", {"key_result": self.name})

			from okr_management.utils.okr_calculations import get_key_result_progress

			self.target_progress = get_key_result_progress(self.name, self)
			self.score = self.target_progress
		else:
			self.action_item_count = 0
			self.checkin_count = 0
			self.target_progress = 0.0
			self.score = 0.0

	def validate(self) -> None:
		self.inherit_context_from_objective()
		self.validate_required_fields()
		self.validate_options()
		self.validate_measurement()
		self.validate_duplicate_title_in_objective()
		self.validate_dates_inside_objective()
		self.validate_target_period()
		self.validate_child_due_dates()
		self.validate_lifecycle()
		self.validate_inherited_fields_locked()

	def validate_duplicate_title_in_objective(self) -> None:
		duplicate = frappe.db.exists(
			"OKR Key Result",
			{
				"name": ["!=", self.name],
				"objective": self.objective,
				"key_result_title": self.key_result_title,
			},
		)
		if duplicate:
			frappe.throw(_("A Key Result with this title already exists in the selected Objective."))

	def validate_dates_inside_objective(self) -> None:
		if not self.objective:
			return
		objective_dates = frappe.db.get_value(
			"OKR Objective", self.objective, ["start_date", "end_date"], as_dict=True
		)
		if not objective_dates or not objective_dates.start_date or not objective_dates.end_date:
			return

		if self.start_date and getdate(self.start_date) < getdate(objective_dates.start_date):
			frappe.throw(
				_("Start Date cannot be before the Parent Objective's Start Date ({0}).").format(
					objective_dates.start_date
				)
			)
		if self.start_date and getdate(self.start_date) > getdate(objective_dates.end_date):
			frappe.throw(
				_("Start Date cannot be after the Parent Objective's End Date ({0}).").format(
					objective_dates.end_date
				)
			)

		if self.end_date and getdate(self.end_date) < getdate(objective_dates.start_date):
			frappe.throw(
				_("Target Date cannot be before the Parent Objective's Start Date ({0}).").format(
					objective_dates.start_date
				)
			)
		if self.end_date and getdate(self.end_date) > getdate(objective_dates.end_date):
			frappe.throw(
				_("Target Date cannot be after the Parent Objective's End Date ({0}).").format(
					objective_dates.end_date
				)
			)

		if self.start_date and self.end_date and getdate(self.start_date) > getdate(self.end_date):
			frappe.throw(_("Start Date cannot be after Target Date."))

	def validate_target_period(self) -> None:
		if not self.parent_plan or not self.end_date:
			return

		target_date = getdate(self.end_date)
		selected = next(
			(
				row
				for row in get_derived_periods(self.parent_plan)
				if getdate(row["start_date"]) <= target_date <= getdate(row["end_date"])
			),
			None,
		)
		if not selected:
			frappe.throw(_("Target Date must be inside the selected Plan timeline."))

		# Target Period is system-derived from Target Date and Plan frequency.
		self.target_period = selected["label"]

	def validate_child_due_dates(self) -> None:
		if not self.name or not self.end_date:
			return
		action_items = frappe.get_all(
			"OKR Action Item",
			filters={"parent_key_result": self.name},
			fields=["name", "due_date"],
		)
		outside = [
			row.name
			for row in action_items
			if row.due_date
			and not (getdate(self.start_date) <= getdate(row.due_date) <= getdate(self.end_date))
		]
		if outside:
			frappe.throw(_("Target Date cannot exclude existing Action Item Due Dates."))

	def validate_lifecycle(self) -> None:
		if self.status == "Active":
			parent_status = frappe.db.get_value(
				"OKR Objective", self.objective, ["status", "parent_plan"], as_dict=True
			)
			plan_status = (
				frappe.db.get_value("OKR Plan", parent_status.parent_plan, "status")
				if parent_status and parent_status.parent_plan
				else None
			)
			if not parent_status or parent_status.status != "Active":
				frappe.throw(_("Key Result cannot become Active unless Parent Objective is Active."))
			if plan_status != "Active":
				frappe.throw(_("Key Result cannot become Active unless Parent Plan is Active."))

			start = self.start_date
			end = self.end_date
			if start and getdate(today()) < getdate(start):
				frappe.throw(_("Key Result cannot be activated before its Start Date ({0}).").format(start))
			if end and getdate(today()) > getdate(end):
				frappe.throw(_("Key Result cannot be activated after its End Date ({0}).").format(end))

	def inherit_context_from_objective(self) -> None:
		if not self.objective:
			self.clear_inherited_context()
			return

		if not frappe.db.exists("OKR Objective", self.objective):
			return

		objective = frappe.db.get_value(
			"OKR Objective",
			self.objective,
			[
				"parent_plan",
				"objective_title",
				"company",
				"financial_year",
				"group",
				"department",
				"plan_owner",
				"owner_user",
				"level",
				"start_date",
				"end_date",
			],
			as_dict=True,
		)
		if not objective:
			self.clear_inherited_context()
			return

		self.parent_plan = objective.parent_plan
		self.objective_title = objective.objective_title
		self.company = objective.company
		self.financial_year = objective.financial_year
		self.group = objective.group
		self.department = objective.department
		self.plan_owner = objective.plan_owner
		self.objective_owner = objective.owner_user
		self.objective_level = objective.level
		self.start_date = self.start_date or objective.start_date
		self.end_date = self.end_date or objective.end_date

	def clear_inherited_context(self) -> None:
		for fieldname in INHERITED_FIELDS:
			setattr(self, fieldname, None)

	# Placeholder setter removed

	def validate_required_fields(self) -> None:
		required = {
			"key_result_title": _("Key Result Title"),
			"objective": _("Parent Objective"),
			"owner_user": _("Key Result Owner"),
			"priority": _("Priority"),
			"status": _("Status"),
			"calculation_mode": _("Calculation Mode"),
			"metric_type": _("Measurement Type"),
			"metric_direction": _("Goal Direction"),
			"end_date": _("Target Date"),
		}
		for fieldname, label in required.items():
			if not self.get(fieldname):
				frappe.throw(_("{0} is required.").format(label))

		if not frappe.db.exists("OKR Objective", self.objective):
			frappe.throw(_("Parent Objective does not exist."))

	def validate_options(self) -> None:
		if self.priority not in VALID_PRIORITIES:
			frappe.throw(_("Priority must be Low, Medium, or High."))
		if self.status not in VALID_STATUSES:
			frappe.throw(_("Status must be Draft, Planned, Active, On Hold, Completed, Closed, or Archived."))
		if self.calculation_mode not in VALID_CALCULATION_MODES:
			frappe.throw(_("Calculation Mode must be Manual or Automatic."))
		if self.metric_type not in VALID_MEASUREMENT_TYPES:
			frappe.throw(_("Measurement Type must be Percentage, Number, Currency, or Boolean."))
		if self.metric_direction not in VALID_MEASUREMENT_DIRECTIONS:
			frappe.throw(_("Goal Direction must be Increase or Decrease."))

	def validate_measurement(self) -> None:
		if self.metric_type != "Currency":
			self.currency = None

		if self.metric_type in ["Percentage", "Boolean"] and self.target_value is None:
			frappe.throw(_("Target Value is required for Measurement Type {0}.").format(self.metric_type))

		if self.calculation_mode == "Automatic" and self.get_doc_before_save():
			if self.has_value_changed("current_value"):
				frappe.throw(_("Current Value is editable only when Calculation Mode is Manual."))

		if self.calculation_mode == "Automatic" and self.is_new() and self.current_value:
			frappe.throw(_("Current Value is editable only when Calculation Mode is Manual."))

	def validate_inherited_fields_locked(self) -> None:
		if self.is_new():
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		if self.has_value_changed("objective"):
			return

		for fieldname in INHERITED_FIELDS:
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} is inherited from Parent Objective and cannot be changed manually.").format(
						self.meta.get_label(fieldname)
					)
				)

	def on_update(self) -> None:
		self.resync_action_item_context_after_objective_move()
		from okr_management.utils.okr_calculations import recalculate_objective_progress

		recalculate_objective_progress(self.objective)

	def resync_action_item_context_after_objective_move(self) -> None:
		"""Refresh denormalized hierarchy fields on children after a KR move."""
		previous = self.get_doc_before_save()
		if not previous or previous.objective == self.objective:
			return
		for action_name in frappe.get_all(
			"OKR Action Item", filters={"parent_key_result": self.name}, pluck="name"
		):
			action = frappe.get_doc("OKR Action Item", action_name)
			action.flags.ignore_permissions = True
			action.save()

	def on_trash(self) -> None:
		if frappe.db.count("OKR Action Item", {"parent_key_result": self.name}) > 0:
			frappe.throw(_("Cannot delete Key Result because dependent Action Items exist."))

	def after_delete(self) -> None:
		from okr_management.utils.okr_calculations import recalculate_objective_progress

		recalculate_objective_progress(self.objective)

	# Placeholder validation removed


@frappe.whitelist()
def get_target_period_options(objective: str) -> list[dict]:
	if not frappe.has_permission("OKR Objective", "read", doc=objective):
		frappe.throw(_("You do not have access to this Objective."), frappe.PermissionError)
	plan_name = frappe.db.get_value("OKR Objective", objective, "parent_plan")
	return [
		{
			"label": row["label"],
			"start_date": str(row["start_date"]),
			"end_date": str(row["end_date"]),
		}
		for row in get_derived_periods(plan_name)
	]
