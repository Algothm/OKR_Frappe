from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from okr_management.utils.okr_calculations import recalculate_sprint_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_percentage, ensure_required_link


class OKRObjective(Document):
	def before_validate(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
		
		if self.sprint and frappe.db.exists("OKR Sprint", self.sprint):
			sprint = frappe.db.get_value("OKR Sprint", self.sprint, ["start_date", "end_date"], as_dict=True)
			if sprint:
				if sprint.start_date:
					self.start_date = sprint.start_date
				if sprint.end_date:
					self.end_date = sprint.end_date

		if self.level == "Organization":
			self.department = None

	def validate(self) -> None:
		ensure_required_link(self.sprint, "Parent Sprint")
		ensure_required_link(self.company, "Organization")
		ensure_required_link(self.owner_user, "Owner User")
		ensure_date_range(self.start_date, self.end_date, "Objective")
		
		if self.level == "Department" and not self.department:
			frappe.throw("Department is required when Level is Department.")

		if self.sprint:
			sprint = frappe.db.get_value("OKR Sprint", self.sprint, ["start_date", "end_date"], as_dict=True)
			if sprint:
				if self.start_date and sprint.start_date and getdate(self.start_date) < getdate(sprint.start_date):
					frappe.throw("Objective Start Date cannot be before the Parent Sprint Start Date.")
				if self.end_date and sprint.end_date and getdate(self.end_date) > getdate(sprint.end_date):
					frappe.throw("Objective End Date cannot be after the Parent Sprint End Date.")
		
		if self.parent_objective and self.parent_objective == self.name:
			frappe.throw("An objective cannot align to itself.")
		ensure_percentage(self.progress, "Progress")

	def on_update(self) -> None:
		# Recalculate parent Sprint progress
		from okr_management.utils.okr_calculations import recalculate_sprint_progress
		recalculate_sprint_progress(self.sprint)
