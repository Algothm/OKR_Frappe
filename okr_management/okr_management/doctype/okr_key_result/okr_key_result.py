from __future__ import annotations

from frappe.model.document import Document
from frappe.utils import flt

from okr_management.utils.okr_calculations import recalculate_key_result_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


class OKRKeyResult(Document):
	def before_validate(self) -> None:
		for action_item in self.get('action_items') or []:
			action_item.parent_key_result = self.name

		if self.get('action_items'):
			progress_values = [flt(row.progress) for row in self.get('action_items')]
			progress = round(sum(progress_values) / len(progress_values), 2)
			self.target_progress = progress
			self.score = progress

	def validate(self) -> None:
		ensure_required_link(self.objective, 'Parent Objective')
		ensure_required_link(self.description, 'Description')
		ensure_required_link(self.target_value, 'Target')
		ensure_percentage(self.target_progress, 'Progress')

		for action_item in self.get('action_items') or []:
			ensure_percentage(action_item.progress, 'Action Item Progress %')
			ensure_percentage(action_item.weight, 'Action Item Weight %')

	def on_update(self) -> None:
		recalculate_key_result_progress(self.name)
