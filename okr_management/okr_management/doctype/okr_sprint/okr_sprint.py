from __future__ import annotations

from frappe.model.document import Document

from okr_management.utils.okr_calculations import recalculate_plan_progress, recalculate_sprint_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_required_link


class OKRSprint(Document):
	def validate(self) -> None:
		ensure_required_link(self.parent_plan, 'Parent Plan')
		ensure_required_link(self.sprint_name, 'Sprint Name')
		ensure_required_link(self.sprint_cycle, 'Sprint Cycle')
		ensure_required_link(self.start_date, 'Start Date')
		ensure_required_link(self.end_date, 'End Date')
		ensure_date_range(self.start_date, self.end_date, 'Sprint')

	def on_update(self) -> None:
		recalculate_sprint_progress(self.name)
		recalculate_plan_progress(self.parent_plan)
