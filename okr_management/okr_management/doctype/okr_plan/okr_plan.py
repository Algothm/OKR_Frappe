from __future__ import annotations

from frappe.model.document import Document

from okr_management.utils.okr_calculations import recalculate_plan_progress
from okr_management.utils.okr_validations import ensure_required_link


class OKRPlan(Document):
	def validate(self) -> None:
		ensure_required_link(self.financial_year, 'Financial Year')
		ensure_required_link(self.plan_name, 'Plan Name')
		ensure_required_link(self.company, 'Organization')
		ensure_required_link(self.status, 'Status')

	def on_update(self) -> None:
		recalculate_plan_progress(self.name)
