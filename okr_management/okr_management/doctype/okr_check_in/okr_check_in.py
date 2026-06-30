from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt, nowdate

from okr_management.utils.okr_calculations import sync_checkin_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


MANAGER_REVIEW_ROLES = {"System Manager", "OKR Admin", "OKR Manager", "Team Lead"}


def user_can_review_checkin() -> bool:
	return bool(MANAGER_REVIEW_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def value_changed(doc: Document, fieldname: str) -> bool:
	if doc.is_new():
		value = doc.get(fieldname)
		return value not in (None, "", "Draft", "Approved")
	previous = doc.get_doc_before_save()
	if not previous:
		return False
	return doc.get(fieldname) != previous.get(fieldname)


class OKRCheckIn(Document):
	def before_validate(self) -> None:
		if not self.reported_by:
			self.reported_by = frappe.session.user
		if self.key_result and frappe.db.exists("OKR Key Result", self.key_result):
			key_result = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				["objective", "cycle", "start_date", "end_date", "baseline_value", "target_value", "metric_direction", "department"],
				as_dict=True
			)
			if key_result:
				if not self.objective:
					self.objective = key_result.objective
				if not self.cycle:
					self.cycle = key_result.cycle
				if not self.department:
					self.department = key_result.department

				# Auto-calculate progress based on raw current_value and direction
				baseline = flt(key_result.baseline_value)
				target = flt(key_result.target_value)
				current = flt(self.current_value)

				if target == baseline:
					self.progress = 0.0
				elif key_result.metric_direction == "Decrease":
					self.progress = min(100.0, max(0.0, ((baseline - current) / (baseline - target)) * 100.0))
				else:
					self.progress = min(100.0, max(0.0, ((current - baseline) / (target - baseline)) * 100.0))
				
				self.progress_percent = self.progress

	def validate(self) -> None:
		ensure_required_link(self.key_result, "Key Result")
		ensure_required_link(self.objective, "Objective")
		ensure_required_link(self.cycle, "OKR Cycle")
		ensure_required_link(self.reported_by, "Reported By")
		ensure_percentage(self.progress, "Progress")

		if self.key_result:
			kr_data = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				["objective", "cycle", "start_date", "end_date", "approval_status"],
				as_dict=True
			)
			if kr_data:
				if kr_data.approval_status != "Approved":
					frappe.throw(f"Check-Ins can only be submitted against Approved Key Results. Current Key Result approval status is '{kr_data.approval_status}'.")
				if self.objective != kr_data.objective:
					frappe.throw("Check-In Objective must match the selected Key Result Objective.")
				if self.cycle != kr_data.cycle:
					frappe.throw("Check-In Cycle must match the selected Key Result Cycle.")
				if self.checkin_date and kr_data.start_date and getdate(self.checkin_date) < getdate(kr_data.start_date):
					frappe.throw("Check-in Date cannot be before the Key Result Start Date.")
				if self.checkin_date and kr_data.end_date and getdate(self.checkin_date) > getdate(kr_data.end_date):
					frappe.throw("Check-in Date cannot be after the Key Result End Date.")

		# Lock manager/review/escalation fields for non-managers
		manager_fields = (
			"review_status", "manager_feedback", "action_required", "review_date", "reviewed_by",
			"escalate_to_department", "reason_for_escalation", "expected_resolution_date"
		)
		is_manager = user_can_review_checkin()
		if not is_manager:
			if any(value_changed(self, fieldname) for fieldname in manager_fields):
				frappe.throw("Only an OKR Manager, Team Lead, OKR Admin, or System Manager can update Review and Escalation fields.")
		else:
			# Auto-fill reviewed_by and review_date when a review action is taken
			if any(value_changed(self, f) for f in ("review_status", "manager_feedback", "action_required")):
				self.reviewed_by = frappe.session.user
				self.review_date = nowdate()

		# Dependency validations
		if self.has_dependency:
			if not self.dependent_department:
				frappe.throw("Dependent Department is required when Has Dependency is checked.")
			if not self.dependency_description:
				frappe.throw("Dependency Description is required when Has Dependency is checked.")

		# Escalation validations
		if self.review_status == "Escalated":
			if not self.escalate_to_department:
				frappe.throw("Escalate To Department is required when Review Status is Escalated.")
			if not self.reason_for_escalation:
				frappe.throw("Reason for Escalation is required when Review Status is Escalated.")

	def on_update(self) -> None:
		sync_checkin_progress(self)

