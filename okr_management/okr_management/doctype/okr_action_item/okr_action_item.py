from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


class OKRActionItem(Document):
	def before_validate(self) -> None:
		self.status = self.status or "Open"
		self.priority = self.priority or "Medium"
		self.progress = flt(self.progress or 0.0)
		self.sync_assigned_to_owner()
		self.owner_user = self.owner_user or frappe.session.user

		self.set_parent_key_result_from_child_context()
		self.inherit_context_from_key_result()

	def validate(self) -> None:
		ensure_required_link(self.action_item_title, "Action Item Title")
		ensure_required_link(self.parent_key_result, "Key Result")
		self.validate_assigned_to()
		ensure_required_link(self.status, "Status")
		ensure_percentage(self.progress, "Progress %")
		self.validate_parent_context()
		self.validate_due_date()
		self.validate_lifecycle()

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
		# Handle completion_date
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
