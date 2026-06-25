from __future__ import annotations

from frappe.model.document import Document

from okr_management.utils.okr_validations import ensure_positive_integer, ensure_required_link


class OKRApprovalMatrix(Document):
	def validate(self) -> None:
		ensure_required_link(self.company, "Company")
		ensure_required_link(self.approver_role, "Approver Role")
		ensure_required_link(self.document_type, "Document Type")
		ensure_positive_integer(self.approval_level, "Approval Level")
