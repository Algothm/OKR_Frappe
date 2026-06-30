from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt

from okr_management.utils.okr_calculations import recalculate_from_key_result
from okr_management.utils.okr_validations import ensure_date_range, ensure_percentage, ensure_required_link, ensure_valid_weight


class OKRKeyResult(Document):
	def before_validate(self) -> None:
		if self.objective and frappe.db.exists("OKR Objective", self.objective):
			objective = frappe.db.get_value("OKR Objective", self.objective, ["cycle", "owner_user", "start_date", "end_date", "department"], as_dict=True)
			if objective:
				if not self.cycle:
					self.cycle = objective.cycle
				if not self.owner_user:
					self.owner_user = objective.owner_user
				if not self.start_date:
					self.start_date = objective.start_date
				if not self.end_date:
					self.end_date = objective.end_date
				if not self.department:
					self.department = objective.department
				if not self.assigned_by:
					self.assigned_by = objective.owner_user

		baseline = flt(self.baseline_value)
		target = flt(self.target_value)
		current = flt(self.current_value)
		if target == baseline:
			self.target_progress = 0.0
		elif self.metric_direction == "Decrease":
			self.target_progress = min(100.0, max(0.0, ((baseline - current) / (baseline - target)) * 100.0))
		else:
			self.target_progress = min(100.0, max(0.0, ((current - baseline) / (target - baseline)) * 100.0))

	def validate(self) -> None:
		ensure_required_link(self.objective, "Objective")
		ensure_required_link(self.cycle, "OKR Cycle")
		ensure_required_link(self.owner_user, "Owner User")
		ensure_date_range(self.start_date, self.end_date, "Key Result")
		ensure_percentage(self.target_progress, "Progress")
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

		# Lock planning fields if approved
		if not self.is_new():
			prev_doc = self.get_doc_before_save()
			if prev_doc and prev_doc.approval_status == "Approved":
				planning_fields = ["baseline_value", "target_value", "metric_type", "metric_direction", "weight"]
				for field in planning_fields:
					if self.get(field) != prev_doc.get(field):
						frappe.throw(f"Cannot modify planning field '{self.meta.get_label(field)}' once the Key Result has been Approved.")

	def on_update(self) -> None:
		recalculate_from_key_result(self.name)

