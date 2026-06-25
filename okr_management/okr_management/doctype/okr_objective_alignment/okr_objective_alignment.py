from __future__ import annotations

from frappe.model.document import Document

from okr_management.utils.okr_validations import ensure_valid_weight


class OKRObjectiveAlignment(Document):
	def validate(self) -> None:
		ensure_valid_weight(self.weight, "Alignment Weight")
