from __future__ import annotations

import frappe
from frappe.model.document import Document

from okr_management.utils.okr_validations import ensure_date_range, ensure_required_link


class OKRCycle(Document):
	def before_validate(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user

	def validate(self) -> None:
		ensure_required_link(self.company, "Company")
		ensure_date_range(self.start_date, self.end_date, "OKR Cycle")
		if self.review_deadline and self.end_date and self.review_deadline < self.end_date:
			frappe.throw("Review Deadline cannot be before the Cycle End Date.")
		if self.status in {"Approved", "Active", "Review in Progress", "Closed"} and not self.cycle_name:
			frappe.throw("Cycle Name is required before the cycle can be approved.")
