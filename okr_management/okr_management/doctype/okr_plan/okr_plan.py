from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from okr_management.utils.okr_calculations import recalculate_plan_progress
from okr_management.utils.okr_validations import ensure_required_link


LOCKED_AFTER_ACTIVE_FIELDS = ("financial_year", "company", "department", "owner_user")
STATUS_TRANSITIONS = {
	"Draft": {"Active"},
	"Active": {"Completed"},
	"Completed": {"Closed"},
	"Closed": {"Archived"},
	"Archived": set(),
}


class OKRPlan(Document):
	def before_validate(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user
		
		# Automatically add the current Plan Owner as the first Owner row if table is empty
		if self.owner_user and not self.get("members"):
			self.append("members", {
				"member_user": self.owner_user,
				"role": "Owner"
			})

		self.preserve_system_calculated_progress()

	def validate(self) -> None:
		ensure_required_link(self.financial_year, "Financial Year")
		ensure_required_link(self.plan_name, "Plan Name")
		ensure_required_link(self.company, "Organization")
		ensure_required_link(self.status, "Status")
		self.validate_lifecycle()
		self.validate_locked_fields()
		self.validate_team_members()

	def validate_team_members(self) -> None:
		members = self.get("members") or []
		
		# Ensure unique users in the team
		seen_users = set()
		for member in members:
			if not member.member_user:
				continue
			if member.member_user in seen_users:
				frappe.throw(_("User {0} is added more than once in the Plan Team.").format(member.member_user))
			seen_users.add(member.member_user)
			
		# Filter roles that are Owner
		owners = [m for m in members if m.role == "Owner"]
		if not owners:
			frappe.throw(_("At least one Owner must always exist in the Plan Team."))
			
		# Keep owner_user in sync with the first Owner in the table
		self.owner_user = owners[0].member_user

	def on_update(self) -> None:
		recalculate_plan_progress(self.name)

	def on_trash(self) -> None:
		self.validate_no_dependents_before_delete()

	def validate_lifecycle(self) -> None:
		if self.is_new():
			if self.status != "Draft":
				frappe.throw(_("New OKR Plans must start in Draft status."))
			return

		previous = self.get_doc_before_save()
		if not previous or previous.status == self.status:
			return

		if self.status not in STATUS_TRANSITIONS.get(previous.status, set()):
			frappe.throw(
				_("OKR Plan status cannot move from {0} to {1}.").format(previous.status, self.status)
			)

		if previous.status == "Draft" and self.status == "Active":
			self.validate_activation_requirements()

		elif previous.status == "Completed" and self.status == "Closed":
			self.validate_closing_requirements()

	def validate_activation_requirements(self) -> None:
		if self.status != "Active":
			return
		ensure_required_link(self.financial_year, "Financial Year")
		ensure_required_link(self.plan_name, "Plan Name")
		ensure_required_link(self.company, "Organization")
		ensure_required_link(self.owner_user, "Plan Owner")

	def validate_locked_fields(self) -> None:
		if self.is_new():
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		if previous.status != "Draft":
			self.validate_fields_unchanged(previous, LOCKED_AFTER_ACTIVE_FIELDS)

	def validate_fields_unchanged(self, previous: Document, fieldnames: tuple[str, ...]) -> None:
		for fieldname in fieldnames:
			if previous.get(fieldname) != self.get(fieldname):
				label = self.meta.get_label(fieldname) or fieldname
				frappe.throw(_("{0} cannot be changed after an OKR Plan becomes Active.").format(label))

	def validate_closing_requirements(self) -> None:
		active_sprint = frappe.db.exists("OKR Sprint", {"parent_plan": self.name, "status": "Active"})
		if active_sprint:
			frappe.throw(_("OKR Plan cannot be Closed while dependent OKR Sprints are still Active."))

		active_objective = frappe.db.exists("OKR Objective", {"parent_plan": self.name, "status": "Active"})
		if active_objective:
			frappe.throw(_("OKR Plan cannot be Closed while dependent OKR Objectives are still Active."))

	def preserve_system_calculated_progress(self) -> None:
		if self.is_new():
			self.progress = 0
			return

		self.progress = flt(self.get_db_value("progress"))

	def validate_no_dependents_before_delete(self) -> None:
		if frappe.db.exists("OKR Sprint", {"parent_plan": self.name}):
			frappe.throw(_("OKR Plan cannot be deleted because dependent OKR Sprints exist."))

		if frappe.db.exists("OKR Objective", {"parent_plan": self.name}):
			frappe.throw(_("OKR Plan cannot be deleted because dependent OKR Objectives exist."))

