from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from okr_management.utils.okr_validations import ensure_date_range


class OKRSprint(Document):
	def validate(self) -> None:
		ensure_date_range(self.start_date, self.end_date, "Sprint")
