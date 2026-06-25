from __future__ import annotations

from frappe.model.document import Document

from okr_management.utils.okr_validations import ensure_required_link, ensure_valid_weight


class OKRInitiative(Document):
	def validate(self) -> None:
		if not self.objective and not self.key_result:
			ensure_required_link(None, "Objective or Key Result")
		ensure_valid_weight(self.weight, "Weight")
