from __future__ import annotations

from frappe.model.document import Document

from okr_management.utils.okr_validations import ensure_required_link


class OKRScoreSnapshot(Document):
	def validate(self) -> None:
		ensure_required_link(self.cycle, "OKR Cycle")
