from __future__ import annotations

import frappe
from frappe.model.document import Document

from okr_management.utils.okr_calculations import recalculate_key_result_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


class OKRActionItem(Document):
	def validate(self) -> None:
		if self.parenttype == 'OKR Key Result' and self.parent:
			self.parent_key_result = self.parent
		ensure_required_link(self.action_item_title, 'Action Item')
		ensure_required_link(self.owner_user, 'Owner')
		ensure_required_link(self.status, 'Status')
		ensure_percentage(self.weight, 'Weight %')
		ensure_percentage(self.progress, 'Progress %')

	def on_update(self) -> None:
		parent = getattr(self, 'parent_key_result', None) or getattr(self, 'parent', None)
		if parent and frappe.db.exists('OKR Key Result', parent):
			recalculate_key_result_progress(parent)
