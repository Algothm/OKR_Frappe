from __future__ import annotations

import frappe
from frappe.model.document import Document


class OKRPlan(Document):
	def before_validate(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user

	def validate(self) -> None:
		pass
