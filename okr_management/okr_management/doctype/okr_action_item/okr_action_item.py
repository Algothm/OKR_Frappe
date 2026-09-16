from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.utils.okr_calculations import calculate_action_item_progress
from okr_management.utils.okr_validations import ensure_max_length, ensure_percentage, ensure_required_link


class OKRActionItem(Document):
	def before_validate(self) -> None:
		# Normalize the legacy stored label without requiring a destructive data migration.
		if self.status == "Archived":
			self.status = "Done"
		self.status = self.status or "Open"
		self.priority = self.priority or "Medium"
		self.progress = flt(self.progress or 0.0)
		self.sync_assigned_to_owner()
		self.owner_user = self.owner_user or frappe.session.user

		self.set_parent_key_result_from_child_context()
		self.inherit_context_from_key_result()
		self.update_measurement_customization_status()
		self.progress = calculate_action_item_progress(self)

	def validate(self) -> None:
		ensure_required_link(self.action_item_title, "Action Item Title")
		ensure_max_length(self.action_item_title, "Action Item Title")
		ensure_required_link(self.parent_key_result, "Key Result")
		self.validate_assigned_to()
		ensure_required_link(self.status, "Status")
		ensure_percentage(self.progress, "Progress %")
		self.validate_parent_context()
		self.validate_due_date()
		self.validate_lifecycle()
		self.validate_measurement_customization()

	def on_update(self) -> None:
		self.update_parent_action_item_count()
		if self.parent_key_result:
			from okr_management.utils.okr_calculations import recalculate_key_result_progress

			recalculate_key_result_progress(self.parent_key_result)

	def on_trash(self) -> None:
		self.update_parent_action_item_count(delta=-1)

	def after_delete(self) -> None:
		if self.parent_key_result:
			from okr_management.utils.okr_calculations import recalculate_key_result_progress

			recalculate_key_result_progress(self.parent_key_result)

	def set_parent_key_result_from_child_context(self) -> None:
		if self.parent_key_result:
			return

		if self.parenttype == "OKR Key Result" and self.parent:
			self.parent_key_result = self.parent
		elif self.parenttype == "OKR Check In" and self.parent:
			self.parent_key_result = frappe.db.get_value("OKR Check In", self.parent, "key_result")

	def inherit_context_from_key_result(self) -> None:
		if self.parent_key_result and frappe.db.exists("OKR Key Result", self.parent_key_result):
			parent_kr = frappe.get_doc("OKR Key Result", self.parent_key_result)
			self.parent_objective = parent_kr.objective
			self.objective_title = parent_kr.objective_title
			self.parent_plan = parent_kr.parent_plan
			self.company = parent_kr.company
			self.group = parent_kr.group or (frappe.db.get_value("OKR Objective", parent_kr.objective, "group") if parent_kr.objective else None)
			self.department = parent_kr.department
			self.financial_year = parent_kr.financial_year
			self.context_start_date = parent_kr.start_date
			self.context_end_date = parent_kr.end_date
			self.key_result_title = parent_kr.key_result_title
			if parent_kr.parent_plan and frappe.db.exists("OKR Plan", parent_kr.parent_plan):
				plan = frappe.db.get_value(
					"OKR Plan",
					parent_kr.parent_plan,
					["sprint_frequency", "description"],
					as_dict=True,
				)
				self.plan_title = frappe.db.get_value("OKR Plan", parent_kr.parent_plan, "plan_name")
				self.plan_description = plan.description
				self.sprint_frequency = plan.sprint_frequency
			if not self.reviewer:
				self.reviewer = parent_kr.reviewer

			measurement_locked = parent_kr.lock_measurement_fields_for_action_item_assignees in (0, "0", None)
			if not self.customize_measurement:
				if self.is_new() or measurement_locked:
					self.metric_type = parent_kr.metric_type or "Percentage"
					self.metric_direction = parent_kr.metric_direction or "Increase"
					self.baseline_value = flt(parent_kr.baseline_value)
					self.target_value = flt(parent_kr.target_value)
				elif not self.metric_type or not self.metric_direction:
					# Preserve populated legacy values; fill only genuinely missing configuration.
					self.metric_type = self.metric_type or parent_kr.metric_type or "Percentage"
					self.metric_direction = self.metric_direction or parent_kr.metric_direction or "Increase"
				if not measurement_locked:
					# Initialize once; later Action Item values remain independent of KR changes.
					if self.is_new():
						self.current_value = flt(parent_kr.baseline_value)
					self.customize_measurement = 1
					self.flags.measurement_initialized_from_parent = True

	def update_measurement_customization_status(self) -> None:
		if not self.parent_key_result:
			self.measurement_customization_status = "Locked"
			return
		lock_val = frappe.db.get_value(
			"OKR Key Result", self.parent_key_result, "lock_measurement_fields_for_action_item_assignees"
		)
		self.measurement_customization_status = "Allowed" if lock_val not in (0, "0", None) else "Locked"

	def validate_measurement_customization(self) -> None:
		if not self.parent_key_result:
			if self.customize_measurement:
				frappe.throw(_("Cannot customize measurement without a Parent Key Result."), frappe.ValidationError)
			return

		parent_kr = frappe.db.get_value(
			"OKR Key Result",
			self.parent_key_result,
			[
				"name",
				"lock_measurement_fields_for_action_item_assignees",
				"metric_type",
				"metric_direction",
				"baseline_value",
				"target_value",
			],
			as_dict=True,
		)
		if not parent_kr:
			return

		lock_val = parent_kr.lock_measurement_fields_for_action_item_assignees
		self.measurement_customization_status = "Allowed" if lock_val not in (0, "0", None) else "Locked"

		if not self.customize_measurement:
			self.metric_type = parent_kr.metric_type or "Percentage"
			self.metric_direction = parent_kr.metric_direction or "Increase"
			self.baseline_value = flt(parent_kr.baseline_value)
			self.target_value = flt(parent_kr.target_value)

			if not self.is_new() and self.has_value_changed("current_value"):
				if not getattr(self.flags, "ignore_permissions", False) and frappe.session.user != "Administrator":
					frappe.throw(
						_("Current Value cannot be edited directly when measurement customization is OFF."),
						frappe.PermissionError,
					)
			return

		is_new = self.is_new()
		prev = self.get_doc_before_save() if not is_new else None
		customization_modified = is_new or (prev and (
			self.has_value_changed("customize_measurement")
			or self.has_value_changed("metric_type")
			or self.has_value_changed("metric_direction")
			or self.has_value_changed("baseline_value")
			or self.has_value_changed("target_value")
			or self.has_value_changed("current_value")
		))

		user = frappe.session.user
		is_admin = (
			user == "Administrator"
			or getattr(self.flags, "ignore_permissions", False)
			or bool({"System Manager", "OKR Admin"} & set(frappe.get_roles(user)))
		)

		if (
			customization_modified
			and not is_admin
			and not getattr(self.flags, "measurement_initialized_from_parent", False)
		):
			if lock_val in (0, "0", None):
				frappe.throw(
					_("Measurement customization is locked by the Key Result owner."),
					frappe.PermissionError,
				)

			employees = set(
				frappe.get_all(
					"Employee",
					filters={"user_id": user, "status": "Active"},
					pluck="name",
				)
			)
			is_assigned = (self.assigned_to == user or self.assigned_to in employees)
			if not is_assigned:
				frappe.throw(
					_("Only the assigned user can customize measurement for this Action Item."),
					frappe.PermissionError,
				)

			if prev and prev.parent_key_result != self.parent_key_result:
				frappe.throw(
					_("Cannot change Parent Key Result while customizing measurement."),
					frappe.PermissionError,
				)

			if self.status not in ("Open", "In Progress", "On Hold", "Blocked"):
				frappe.throw(
					_("Measurement customization is only permitted for active Action Items."),
					frappe.ValidationError,
				)

	def sync_assigned_to_owner(self) -> None:
		if not self.assigned_to:
			return

		if frappe.db.exists("User", self.assigned_to):
			self.owner_user = self.assigned_to
		else:
			employee_user = frappe.db.get_value("Employee", self.assigned_to, "user_id")
			if employee_user:
				self.owner_user = employee_user

	def validate_assigned_to(self) -> None:
		ensure_required_link(self.assigned_to, "Assigned To")
		if not (frappe.db.exists("User", self.assigned_to) or frappe.db.exists("Employee", self.assigned_to)):
			frappe.throw(_("Assigned To User does not exist."))
		if frappe.db.exists("User", self.assigned_to) and not frappe.db.get_value(
			"User", self.assigned_to, "enabled"
		):
			frappe.throw(_("Assigned To User must be enabled."))

	def validate_parent_context(self) -> None:
		if not self.parent_key_result:
			frappe.throw(_("Parent Key Result is required."))
		if not frappe.db.exists("OKR Key Result", self.parent_key_result):
			frappe.throw(_("Parent Key Result does not exist."))

	def validate_due_date(self) -> None:
		ensure_required_link(self.due_date, "Due Date")
		if not self.parent_key_result:
			return
		parent_dates = frappe.db.get_value(
			"OKR Key Result",
			self.parent_key_result,
			["start_date", "end_date", "parent_plan", "target_period"],
			as_dict=True,
		)
		if not parent_dates:
			return
		if parent_dates.start_date and getdate(self.due_date) < getdate(parent_dates.start_date):
			frappe.throw(_("Due Date cannot be before the Parent Key Result's timeline."))
		if parent_dates.end_date and getdate(self.due_date) > getdate(parent_dates.end_date):
			frappe.throw(_("Due Date cannot be after the Parent Key Result's Target Date."))

	def validate_lifecycle(self) -> None:
		if self.status == "Completed":
			if not self.completion_date:
				self.completion_date = today()
		else:
			self.completion_date = None

	def update_parent_action_item_count(self, delta: int = 0) -> None:
		if not self.parent_key_result or not frappe.db.exists("OKR Key Result", self.parent_key_result):
			return

		count = frappe.db.count("OKR Action Item", {"parent_key_result": self.parent_key_result}) + delta
		frappe.db.set_value(
			"OKR Key Result",
			self.parent_key_result,
			"action_item_count",
			max(count, 0),
			update_modified=False,
		)
