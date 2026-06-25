from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from okr_management.utils.okr_calculations import get_progress_from_values, recalculate_from_key_result
from okr_management.utils.okr_validations import ensure_date_range, ensure_percentage, ensure_required_link, ensure_valid_weight


class OKRKeyResult(Document):
	def before_validate(self) -> None:
		if self.objective and frappe.db.exists("OKR Objective", self.objective):
			objective = frappe.db.get_value("OKR Objective", self.objective, ["cycle", "owner_user", "start_date", "end_date"], as_dict=True)
			if objective:
				if not self.cycle:
					self.cycle = objective.cycle
				if not self.owner_user:
					self.owner_user = objective.owner_user
				if not self.start_date:
					self.start_date = objective.start_date
				if not self.end_date:
					self.end_date = objective.end_date
		if self.current_value is not None and self.baseline_value is not None and self.target_value is not None:
			self.target_progress = get_progress_from_values(self.baseline_value, self.current_value, self.target_value)

	def validate(self) -> None:
		ensure_required_link(self.objective, "Objective")
		ensure_required_link(self.cycle, "OKR Cycle")
		ensure_required_link(self.owner_user, "Owner User")
		ensure_date_range(self.start_date, self.end_date, "Key Result")
		ensure_percentage(self.target_progress, "Target Progress")
		ensure_valid_weight(self.weight, "Weight")
		if self.objective:
			objective = frappe.db.get_value("OKR Objective", self.objective, ["cycle", "start_date", "end_date"], as_dict=True)
			if objective and objective.cycle and self.cycle != objective.cycle:
				frappe.throw("Key Result Cycle must match the selected Objective Cycle.")
			if objective and self.start_date and objective.start_date and getdate(self.start_date) < getdate(objective.start_date):
				frappe.throw("Key Result Start Date cannot be before the Objective Start Date.")
			if objective and self.end_date and objective.end_date and getdate(self.end_date) > getdate(objective.end_date):
				frappe.throw("Key Result End Date cannot be after the Objective End Date.")
		if self.target_value == self.baseline_value:
			frappe.throw("Target Value must differ from Baseline Value.")
		if self.status in {"Approved", "Active", "Achieved", "Missed", "Closed"} and not self.metric_type:
			frappe.throw("Metric Type is required once a Key Result is approved.")

	def on_update(self) -> None:
		recalculate_from_key_result(self.name)
