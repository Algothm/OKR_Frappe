from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.okr_management.doctype.okr_plan.okr_plan import (
	get_default_objective_dates,
	get_plan_timeline,
)
from okr_management.utils.okr_calculations import recalculate_objective_progress, recalculate_plan_progress

STATUS_TRANSITIONS = {
	"Draft": {"Active"},
	"Active": {"On Hold", "Completed", "Closed"},
	"On Hold": {"Active", "Completed", "Closed"},
	"Completed": {"Closed"},
	"Closed": set(),
}

SETUP_LOCKED_STATUSES = {"Closed"}
ACTIVE_LOCKED_STATUSES = {"Closed"}
PLAN_ACTIVE_REQUIRED_STATUSES = {"Active", "On Hold", "Completed", "Closed"}
COMPLETED_KR_STATUSES = {"Achieved", "Completed", "Closed"}
GOVERNANCE_ROLES = {"OKR Admin"}
MANAGER_ROLES = {"OKR Admin", "Department Head"}

SETUP_LOCKED_FIELDS = {
	"parent_plan",
	"financial_year",
	"company",
	"plan_owner",
}
ACTIVE_LOCKED_FIELDS = set()
SYSTEM_FIELDS = {"progress", "key_result_count"}


class OKRObjective(Document):
	def before_validate(self) -> None:
		self.status = self.status or "Draft"
		self.priority = self.priority or "High"
		self.level = "Department"
		self.owner_user = self.owner_user or frappe.session.user
		self.inherit_context_from_plan()
		self.sync_group_context()
		self.default_dates_from_plan()
		self.update_system_summary_fields()

	def validate(self) -> None:
		self.validate_required_fields()
		self.validate_parent_relationships()
		self.validate_lifecycle_transition()
		self.validate_parent_status_dependencies()
		self.validate_dates_inside_plan()
		self.validate_child_dates()
		self.validate_duplicate_title_in_plan()
		self.validate_completion_criteria()
		self.validate_locked_fields()
		self.validate_system_fields()

	def on_update(self) -> None:
		values = self.get_system_summary_values()
		if values:
			frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
		recalculate_plan_progress(self.parent_plan)
		archive_plan_when_all_objectives_are_terminal(self.parent_plan)

	def on_trash(self) -> None:
		if self.has_key_results():
			frappe.throw(_("Cannot delete Objective because Key Results exist."))

	def after_delete(self) -> None:
		if self.parent_plan:
			recalculate_plan_progress(self.parent_plan)

	def get_invalid_links(self, is_submittable=False):
		# Dynamic links are checked before before_validate.
		self.level_details_doctype = "Department"
		self.level_details = self.level_details or self.department
		return super().get_invalid_links(is_submittable=is_submittable)

	def exists_in_database(self) -> bool:
		return bool(self.name and frappe.db.exists(self.doctype, self.name))

	def inherit_context_from_plan(self) -> None:
		if not self.parent_plan or not frappe.db.exists("OKR Plan", self.parent_plan):
			return

		plan = frappe.db.get_value(
			"OKR Plan",
			self.parent_plan,
			["financial_year", "company", "owner_user", "status"],
			as_dict=True,
		)
		if not plan:
			return

		self.financial_year = plan.financial_year
		self.company = plan.company
		self.plan_owner = plan.owner_user

	def sync_group_context(self) -> None:
		if not self.group:
			if self.is_new() and not self.department:
				frappe.throw(_("Group is required."))
			return

		group = frappe.db.get_value("Group", self.group, ["company", "disabled"], as_dict=True)
		if not group:
			frappe.throw(_("Selected Group does not exist."))
		if group.disabled:
			frappe.throw(_("Selected Group is disabled."))
		if group.company != self.company:
			frappe.throw(_("Selected Group must belong to the Plan Organization."))

	def default_dates_from_plan(self) -> None:
		if not self.parent_plan or not frappe.db.exists("OKR Plan", self.parent_plan):
			return
		default_start, default_end = get_default_objective_dates(self.parent_plan)
		if default_start and default_end:
			self.start_date = self.start_date or default_start
			self.end_date = self.end_date or default_end
		else:
			start_date, end_date = get_plan_timeline(self.parent_plan)
			self.start_date = self.start_date or start_date
			self.end_date = self.end_date or end_date

	def validate_required_fields(self) -> None:
		required = {
			"objective_title": _("Objective Title"),
			"parent_plan": _("Plan"),
			"level": _("Level"),
			"priority": _("Priority"),
			"company": _("Organization"),
			"owner_user": _("Objective Owner"),
			"status": _("Status"),
		}
		for fieldname, label in required.items():
			if not self.get(fieldname):
				frappe.throw(_("{0} is required.").format(label))

		if self.department:
			if not frappe.db.exists("Department", self.department):
				frappe.throw(_("Selected Department does not exist."))
			department_company = frappe.db.get_value("Department", self.department, "company")
			if department_company and department_company != self.company:
				frappe.throw(_("Selected Department must belong to the Plan Organization."))

	def validate_parent_relationships(self) -> None:
		if not frappe.db.exists("OKR Plan", self.parent_plan):
			frappe.throw(_("Selected Plan does not exist."))

		if self.exists_in_database() and self.has_value_changed("parent_plan"):
			frappe.throw(_("Objective cannot be moved between Plans."))

	def validate_lifecycle_transition(self) -> None:
		old_status = (
			self.get_doc_before_save().status if not self.is_new() and self.get_doc_before_save() else None
		)
		if not old_status or old_status == self.status:
			return

		allowed = STATUS_TRANSITIONS.get(old_status, set())
		if self.status not in allowed:
			frappe.throw(
				_("Invalid Objective status transition from {0} to {1}.").format(old_status, self.status)
			)

		self.validate_transition_actor(old_status, self.status)

	def validate_transition_actor(self, old_status: str, new_status: str) -> None:
		roles = set(frappe.get_roles(frappe.session.user))
		if frappe.session.user == "Administrator" or roles.intersection(GOVERNANCE_ROLES):
			return

		user = frappe.session.user
		if new_status == "Completed" and user in {self.owner_user, self.plan_owner}:
			return
		if new_status == "Active" and user in {self.owner_user, self.plan_owner}:
			return
		if new_status in {"On Hold", "Closed"} and user == self.plan_owner:
			return

		frappe.throw(
			_("You are not allowed to change Objective status from {0} to {1}.").format(
				old_status, new_status
			)
		)

	def validate_parent_status_dependencies(self) -> None:
		plan_status = frappe.db.get_value("OKR Plan", self.parent_plan, "status")
		if not plan_status:
			frappe.throw(_("Parent Plan status is required."))
		if plan_status == "Archived":
			frappe.throw(_("Objective cannot be created or updated under an Archived Plan."))
		if self.status in PLAN_ACTIVE_REQUIRED_STATUSES and plan_status != "Active":
			frappe.throw(_("Objective cannot become {0} unless Parent Plan is Active.").format(self.status))

	def validate_dates_inside_plan(self) -> None:
		start = getdate(self.start_date)
		end = getdate(self.end_date)
		if start > end:
			frappe.throw(_("Objective End Date cannot be before Start Date."))

		plan_start, plan_end = get_plan_timeline(self.parent_plan)
		if start < getdate(plan_start) or end > getdate(plan_end):
			frappe.throw(_("Objective dates must stay within the Plan period."))

	def validate_child_dates(self) -> None:
		if not self.name:
			return
		key_results = frappe.get_all(
			"OKR Key Result",
			filters={"objective": self.name},
			fields=["name", "end_date"],
		)
		outside = [
			row.name
			for row in key_results
			if row.end_date
			and not (getdate(self.start_date) <= getdate(row.end_date) <= getdate(self.end_date))
		]
		if outside:
			frappe.throw(_("Objective timeline cannot exclude existing Key Result Target Dates."))

	def validate_duplicate_title_in_plan(self) -> None:
		duplicate = frappe.db.exists(
			"OKR Objective",
			{
				"name": ["!=", self.name],
				"parent_plan": self.parent_plan,
				"objective_title": self.objective_title,
			},
		)
		if duplicate:
			frappe.throw(_("An Objective with this title already exists in the selected Plan."))

	def validate_completion_criteria(self) -> None:
		if self.status != "Completed":
			return

		key_results = self.get_key_results()
		incomplete = [row for row in key_results if row.get("status") not in COMPLETED_KR_STATUSES]
		if key_results and not incomplete:
			return

		if not self.partial_completion_accepted:
			frappe.throw(
				_(
					"Objective can be completed only when all Key Results are completed or a manager accepts partial completion."
				)
			)

		if not self.is_manager_or_owner_accepting_completion():
			frappe.throw(_("Only a manager or Plan Owner can accept partial Objective completion."))

	def is_manager_or_owner_accepting_completion(self) -> bool:
		roles = set(frappe.get_roles(frappe.session.user))
		return (
			frappe.session.user == "Administrator"
			or bool(roles.intersection(MANAGER_ROLES))
			or frappe.session.user == self.plan_owner
		)

	def validate_locked_fields(self) -> None:
		if self.is_new():
			return
		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		locked_fields = set(SETUP_LOCKED_FIELDS)
		if old_doc.status in {"Closed"}:
			locked_fields.update(
				{
					"objective_title",
					"owner_user",
					"group",
					"department",
					"start_date",
					"end_date",
					"priority",
					"reviewer",
					"description",
					"partial_completion_accepted",
					"completion_notes",
				}
			)

		for fieldname in locked_fields:
			if self.has_value_changed(fieldname):
				frappe.throw(
					_("{0} cannot be changed in the current Objective lifecycle.").format(
						self.meta.get_label(fieldname)
					)
				)

	def validate_system_fields(self) -> None:
		for fieldname, value in self.get_system_summary_values().items():
			setattr(self, fieldname, value)

	def get_key_results(self) -> list[dict[str, Any]]:
		if not self.name:
			return []
		progress_field = (
			"target_progress"
			if frappe.get_meta("OKR Key Result").has_field("target_progress")
			else "progress"
		)
		return frappe.get_all(
			"OKR Key Result",
			filters={"objective": self.name},
			fields=["name", "status", progress_field],
		)

	def has_key_results(self) -> bool:
		return bool(self.name and frappe.db.exists("OKR Key Result", {"objective": self.name}))

	def get_system_summary_values(self) -> dict[str, Any]:
		key_results = self.get_key_results()
		progress_field = (
			"target_progress"
			if frappe.get_meta("OKR Key Result").has_field("target_progress")
			else "progress"
		)
		progress_values = [row.get(progress_field) for row in key_results]
		progress = (
			round(sum(flt(value) for value in progress_values) / len(progress_values), 2)
			if progress_values
			else 0.0
		)
		return {"progress": progress, "key_result_count": len(key_results)}

	def update_system_summary_fields(self) -> None:
		for fieldname, value in self.get_system_summary_values().items():
			setattr(self, fieldname, value)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_team_options(doctype, txt, searchfield, start, page_len, filters):
	users = frappe.get_all(
		"User",
		filters={"enabled": 1},
		or_filters={
			"name": ["like", f"%{txt}%"],
			"full_name": ["like", f"%{txt}%"],
		},
		fields=["name", "full_name"],
		order_by="full_name asc",
		start=start,
		page_length=page_len,
	)
	return [(user.name, user.full_name or user.name) for user in users]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_available_plans(doctype, txt, searchfield, start, page_len, filters):
	"""Return selectable Plan names without granting access to Plan documents."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to select an OKR Plan."), frappe.PermissionError)
	plan_filters = {"status": ["in", ["Draft", "Active"]]}
	requested_status = (filters or {}).get("status") if isinstance(filters, dict) else None
	if requested_status:
		plan_filters["status"] = requested_status
	rows = frappe.get_all(
		"OKR Plan",
		filters=plan_filters,
		or_filters={"name": ["like", f"%{txt}%"], "plan_name": ["like", f"%{txt}%"]},
		fields=["name", "plan_name"],
		order_by="modified desc",
		start=start,
		page_length=page_len,
	)
	return [[row.name, row.plan_name or row.name] for row in rows]


def archive_plan_when_all_objectives_are_terminal(plan_name: str | None) -> None:
	"""Archive a plan after its final objective is completed or closed."""
	if not plan_name or frappe.db.get_value("OKR Plan", plan_name, "status") == "Archived":
		return

	statuses = frappe.get_all(
		"OKR Objective",
		filters={"parent_plan": plan_name},
		pluck="status",
		limit_page_length=10000,
	)
	if statuses and all(status in {"Completed", "Closed"} for status in statuses):
		frappe.db.set_value("OKR Plan", plan_name, "status", "Archived")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_plan_departments(doctype, txt, searchfield, start, page_len, filters):
	"""Return Departments only for the selected Plan's company."""
	from okr_management.permissions import is_okr_admin, is_okr_user

	if not (is_okr_admin() or is_okr_user()):
		frappe.throw(_("Only an OKR User or OKR Admin can select a Department."), frappe.PermissionError)

	parent_plan = (filters or {}).get("parent_plan") if isinstance(filters, dict) else None
	department_filters = {}
	if parent_plan:
		plan = frappe.db.get_value(
			"OKR Plan",
			{"name": parent_plan, "status": ["in", ["Draft", "Active"]]},
			["name", "company"],
			as_dict=True,
		)
		if not plan or not plan.company:
			return []
		department_filters["company"] = plan.company

	rows = frappe.get_all(
		"Department",
		filters=department_filters,
		or_filters={"name": ["like", f"%{txt}%"], "department_name": ["like", f"%{txt}%"]},
		fields=["name", "department_name"],
		order_by="department_name asc",
		start=start,
		page_length=page_len,
	)
	return [[row.name, row.department_name or row.name] for row in rows]
