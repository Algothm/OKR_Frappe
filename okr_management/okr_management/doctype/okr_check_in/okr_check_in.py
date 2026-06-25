from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from okr_management.utils.okr_calculations import sync_checkin_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


MANAGER_REVIEW_ROLES = {"System Manager", "OKR Admin", "OKR Manager", "Team Lead"}


def user_can_review_checkin() -> bool:
	return bool(MANAGER_REVIEW_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def value_changed(doc: Document, fieldname: str) -> bool:
	if doc.is_new():
		value = doc.get(fieldname)
		return value not in (None, "", "Draft")
	previous = doc.get_doc_before_save()
	if not previous:
		return False
	return doc.get(fieldname) != previous.get(fieldname)


class OKRCheckIn(Document):
	def before_validate(self) -> None:
		if not self.reported_by:
			self.reported_by = frappe.session.user
		if self.key_result and frappe.db.exists("OKR Key Result", self.key_result):
			key_result = frappe.db.get_value("OKR Key Result", self.key_result, ["objective", "cycle", "start_date", "end_date"], as_dict=True)
			if key_result:
				if not self.objective:
					self.objective = key_result.objective
				if not self.cycle:
					self.cycle = key_result.cycle

	def validate(self) -> None:
		ensure_required_link(self.key_result, "Key Result")
		ensure_required_link(self.objective, "Objective")
		ensure_required_link(self.cycle, "OKR Cycle")
		ensure_required_link(self.reported_by, "Reported By")
		ensure_percentage(self.progress_percent, "Progress Percent")
		if self.key_result:
			key_result = frappe.db.get_value("OKR Key Result", self.key_result, ["objective", "cycle", "start_date", "end_date"], as_dict=True)
			if key_result and self.objective != key_result.objective:
				frappe.throw("Check-In Objective must match the selected Key Result Objective.")
			if key_result and self.cycle != key_result.cycle:
				frappe.throw("Check-In Cycle must match the selected Key Result Cycle.")
			if key_result and self.checkin_date and key_result.start_date and getdate(self.checkin_date) < getdate(key_result.start_date):
				frappe.throw("Check-in Date cannot be before the Key Result Start Date.")
			if key_result and self.checkin_date and key_result.end_date and getdate(self.checkin_date) > getdate(key_result.end_date):
				frappe.throw("Check-in Date cannot be after the Key Result End Date.")
		if not user_can_review_checkin():
			manager_fields = ("manager_rating", "manager_feedback", "review_status")
			if any(value_changed(self, fieldname) for fieldname in manager_fields):
				frappe.throw("Only an OKR Manager, Team Lead, OKR Admin, or System Manager can update Manager Review fields.")

		if self.review_status in {"Approved", "Modified"} and not self.manager_rating:
			frappe.throw("Manager Rating is required once the check-in is reviewed.")

	def on_update(self) -> None:
		sync_checkin_progress(self)
