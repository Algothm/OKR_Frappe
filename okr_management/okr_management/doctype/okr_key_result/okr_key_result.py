from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt

from okr_management.utils.okr_calculations import recalculate_objective_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_percentage, ensure_required_link, ensure_valid_weight


# Action Item status -> implied progress percentage (used when progress field is 0)
_ACTION_STATUS_PROGRESS = {
	"Completed": 100.0,
	"In Progress": 50.0,
	"Not Started": 0.0,
	"Draft": 0.0,
	"Blocked": 0.0,
	"Cancelled": 0.0,
}


def _progress_from_action_items(action_items) -> float | None:
	"""Return average progress of child action items, or None if list is empty."""
	if not action_items:
		return None
	total = 0.0
	for item in action_items:
		p = flt(item.get("progress") or 0)
		if p == 0:
			p = _ACTION_STATUS_PROGRESS.get(item.get("status") or "Draft", 0.0)
		total += p
	return round(total / len(action_items), 2)


class OKRKeyResult(Document):
	def before_validate(self) -> None:
		if self.objective and frappe.db.exists("OKR Objective", self.objective):
			objective = frappe.db.get_value("OKR Objective", self.objective, ["owner_user", "start_date", "end_date"], as_dict=True)
			if objective:
				if not self.owner_user:
					self.owner_user = objective.owner_user
				if not self.start_date:
					self.start_date = objective.start_date
				if not self.end_date:
					self.end_date = objective.end_date
				if not self.assigned_by:
					self.assigned_by = objective.owner_user

		baseline = flt(self.baseline_value)
		target = flt(self.target_value)

		# Primary: derive progress from child Action Items
		ai_progress = _progress_from_action_items(self.get("action_items") or [])
		if ai_progress is not None:
			self.target_progress = ai_progress
			# Back-calculate current_value so KPI metrics stay consistent
			if target != baseline:
				direction = self.metric_direction or "Increase"
				if direction == "Decrease":
					self.current_value = round(baseline - ((ai_progress / 100.0) * (baseline - target)), 2)
				else:
					self.current_value = round(baseline + ((ai_progress / 100.0) * (target - baseline)), 2)
		else:
			# Fallback: calculate from baseline / current / target
			current = flt(self.current_value)
			if target == baseline:
				self.target_progress = 0.0
			elif self.metric_direction == "Decrease":
				self.target_progress = min(100.0, max(0.0, ((baseline - current) / (baseline - target)) * 100.0))
			else:
				self.target_progress = min(100.0, max(0.0, ((current - baseline) / (target - baseline)) * 100.0))

	def validate(self) -> None:
		ensure_required_link(self.objective, "Objective")
		ensure_required_link(self.owner_user, "Owner User")
		ensure_date_range(self.start_date, self.end_date, "Key Result")
		ensure_percentage(self.target_progress, "Progress")
		ensure_valid_weight(self.weight, "Weight")

		if self.objective:
			objective = frappe.db.get_value("OKR Objective", self.objective, ["start_date", "end_date"], as_dict=True)
			if objective:
				if self.start_date and objective.start_date and getdate(self.start_date) < getdate(objective.start_date):
					frappe.throw("Key Result Start Date cannot be before the Objective Start Date.")
				if self.end_date and objective.end_date and getdate(self.end_date) > getdate(objective.end_date):
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
		recalculate_objective_progress(self.objective)
