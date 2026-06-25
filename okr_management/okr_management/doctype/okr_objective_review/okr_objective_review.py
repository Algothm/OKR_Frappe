from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from okr_management.utils.okr_validations import ensure_required_link


REVIEWER_ROLES = {"System Manager", "OKR Admin", "OKR Manager", "Team Lead"}


def user_can_update_manager_review() -> bool:
	return bool(REVIEWER_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def review_value_changed(doc: Document, fieldname: str) -> bool:
	if doc.is_new():
		value = doc.get(fieldname)
		return value not in (None, "", "Draft", "Approve with Conditions")
	previous = doc.get_doc_before_save()
	if not previous:
		return False
	return doc.get(fieldname) != previous.get(fieldname)


class OKRObjectiveReview(Document):
	def before_validate(self) -> None:
		if self.objective and not self.self_rating:
			self.self_rating = get_derived_self_rating(self.objective)
		if not self.reviewer:
			self.reviewer = frappe.session.user
		if self.objective and frappe.db.exists("OKR Objective", self.objective):
			objective = frappe.db.get_value("OKR Objective", self.objective, ["cycle", "end_date"], as_dict=True)
			if objective and not self.cycle:
				self.cycle = objective.cycle

	def validate(self) -> None:
		ensure_required_link(self.objective, "Objective")
		ensure_required_link(self.cycle, "OKR Cycle")
		ensure_required_link(self.reviewer, "Reviewer")
		if self.objective:
			objective = frappe.db.get_value("OKR Objective", self.objective, ["cycle", "end_date"], as_dict=True)
			if objective and self.cycle != objective.cycle:
				frappe.throw("Objective Review Cycle must match the selected Objective Cycle.")
			if objective and self.review_date and objective.end_date and getdate(self.review_date) < getdate(objective.end_date):
				frappe.msgprint("This review is dated before the Objective End Date. This is allowed for mid-cycle reviews.")
		if not user_can_update_manager_review():
			manager_fields = ("manager_rating", "manager_feedback", "rating", "decision", "review_status", "next_actions")
			if any(review_value_changed(self, fieldname) for fieldname in manager_fields):
				frappe.throw("Only an OKR Manager, Team Lead, OKR Admin, or System Manager can update Manager Decision fields.")

		if self.review_status in {"Approved", "Modified"} and not self.manager_rating:
			frappe.throw("Manager Rating is required when the review is approved or modified.")


@frappe.whitelist()
def get_derived_self_rating(objective: str | None = None) -> float | None:
	if not objective:
		return None
	result = frappe.db.sql(
		"""
		select avg(self_rating)
		from `tabOKR Check In`
		where objective = %s
			and self_rating is not null
			and self_rating != ''
		""",
		(objective,),
	)
	if result and result[0] and result[0][0] is not None:
		return round(float(result[0][0]), 2)
	return None
