from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from okr_management.utils.okr_calculations import recalculate_cycle_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_percentage, ensure_required_link


class OKRObjective(Document):
	def before_validate(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user
		if self.cycle and frappe.db.exists("OKR Cycle", self.cycle):
			cycle = frappe.db.get_value("OKR Cycle", self.cycle, ["company", "start_date", "end_date"], as_dict=True)
			if cycle:
				# The Cycle owns company and period context; keep Objectives exactly aligned.
				if cycle.company:
					self.company = cycle.company
				if cycle.start_date:
					self.start_date = cycle.start_date
				if cycle.end_date:
					self.end_date = cycle.end_date

	def validate(self) -> None:
		ensure_required_link(self.cycle, "OKR Cycle")
		ensure_required_link(self.company, "Company")
		ensure_required_link(self.owner_user, "Owner User")
		ensure_date_range(self.start_date, self.end_date, "Objective")
		if self.start_date and self.end_date and getdate(self.start_date) > getdate(self.end_date):
			frappe.throw("Objective Start Date cannot be after Objective End Date. Please check the selected OKR Cycle dates.")
		ensure_percentage(self.progress, "Progress")
		if self.cycle:
			cycle = frappe.db.get_value("OKR Cycle", self.cycle, ["company", "start_date", "end_date"], as_dict=True)
			if cycle and cycle.company and self.company and cycle.company != self.company:
				frappe.throw("Objective Company must match the selected OKR Cycle Company.")
			if cycle and self.start_date and cycle.start_date and getdate(self.start_date) < getdate(cycle.start_date):
				frappe.throw("Objective Start Date cannot be before the OKR Cycle Start Date.")
			if cycle and self.end_date and cycle.end_date and getdate(self.end_date) > getdate(cycle.end_date):
				frappe.throw("Objective End Date cannot be after the OKR Cycle End Date.")
		if self.parent_objective and self.parent_objective == self.name:
			frappe.throw("An objective cannot align to itself.")

	def on_update(self) -> None:
		recalculate_cycle_progress(self.cycle)
