from __future__ import annotations

import frappe
from frappe.model.document import Document

from okr_management.utils.okr_calculations import recalculate_objective_progress, recalculate_sprint_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


class OKRObjective(Document):
	def before_validate(self) -> None:
		if self.sprint and frappe.db.exists('OKR Sprint', self.sprint):
			sprint = frappe.db.get_value('OKR Sprint', self.sprint, ['parent_plan'], as_dict=True)
			if sprint and sprint.parent_plan:
				self.parent_plan = sprint.parent_plan

		if self.parent_plan and frappe.db.exists('OKR Plan', self.parent_plan):
			plan = frappe.db.get_value('OKR Plan', self.parent_plan, ['company', 'department'], as_dict=True)
			if plan:
				if not self.company:
					self.company = plan.company
				if self.level == 'Department' and plan.department and not self.department:
					self.department = plan.department

		if self.level == 'Organization':
			self.department = None

	def validate(self) -> None:
		ensure_required_link(self.parent_plan, 'Parent Plan')
		ensure_required_link(self.sprint, 'Parent Sprint')
		ensure_required_link(self.level, 'Level')
		ensure_required_link(self.company, 'Organization')
		ensure_required_link(self.description, 'Description')
		ensure_required_link(self.owner_user, 'Owner')
		ensure_percentage(self.progress, 'Progress')

		if self.level == 'Department' and not self.department:
			frappe.throw('Department is required when Level is Department.')

		if self.sprint:
			sprint_plan = frappe.db.get_value('OKR Sprint', self.sprint, 'parent_plan')
			if sprint_plan and self.parent_plan and sprint_plan != self.parent_plan:
				frappe.throw('Parent Plan must match the selected Parent Sprint\'s Parent Plan.')

	def on_update(self) -> None:
		recalculate_objective_progress(self.name)
		recalculate_sprint_progress(self.sprint)
