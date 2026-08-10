from __future__ import annotations

from datetime import timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, get_last_day, getdate

from okr_management.utils.okr_calculations import recalculate_plan_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_required_link


LOCKED_AFTER_ACTIVE_FIELDS = ("financial_year", "company", "owner_user", "sprint_frequency", "planned_activation_date")
STATUS_TRANSITIONS = {
	"Draft": {"Active", "Archived"},
	"Active": {"Draft", "Archived"},
	"Archived": {"Draft", "Active"},
}
SPRINT_FREQUENCIES = {"Monthly", "Quarterly"}


class OKRPlan(Document):
	def before_validate(self) -> None:
		if not self.owner_user:
			self.owner_user = frappe.session.user

		# Automatically add the current Plan Admin as the first Admin row if table is empty
		if self.owner_user and not self.get("members"):
			self.append("members", {
				"member_user": self.owner_user,
				"role": "Admin"
			})

		self.preserve_system_calculated_progress()

	def validate(self) -> None:
		ensure_required_link(self.financial_year, "Financial Year")
		ensure_required_link(self.plan_name, "Plan Name")
		ensure_required_link(self.company, "Organization")
		ensure_required_link(self.status, "Status")
		ensure_required_link(self.sprint_frequency, "Sprint Frequency")
		self.validate_sprint_frequency()
		self.validate_planned_activation_date()
		self.validate_lifecycle()
		self.validate_locked_fields()
		self.validate_team_members()

	def validate_sprint_frequency(self) -> None:
		if self.sprint_frequency not in SPRINT_FREQUENCIES:
			frappe.throw(_("Sprint Frequency must be Monthly or Quarterly."))

	def validate_planned_activation_date(self) -> None:
		if self.status == "Draft" and not self.planned_activation_date:
			frappe.throw(_("Planned Activation Date is required while the Plan is in Draft."))
		if not self.planned_activation_date or not self.financial_year:
			return
		plan_start, plan_end = _fiscal_year_dates(self.financial_year)
		activation_date = getdate(self.planned_activation_date)
		if activation_date < plan_start:
			frappe.throw(_("Planned Activation Date cannot be before the Plan Start Date."))
		if activation_date > plan_end:
			frappe.throw(_("Planned Activation Date must be within the selected Financial Year."))

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

		# Filter roles that are Admin
		owners = [m for m in members if m.role == "Admin"]
		if not owners:
			frappe.throw(_("At least one Admin must always exist in the Plan Team."))

		# Keep owner_user in sync with the first Admin in the table
		self.owner_user = owners[0].member_user

	def on_update(self) -> None:
		recalculate_plan_progress(self.name)
		previous = self.get_doc_before_save()
		if previous and previous.status == "Draft" and self.status == "Active":
			activate_plan_hierarchy(self.name)

	def on_trash(self) -> None:
		self.validate_no_dependents_before_delete()

	def validate_lifecycle(self) -> None:
		if self.is_new():
			if self.status not in {"Draft", "Active"}:
				frappe.throw(_("New OKR Plans must start in Draft or Active status."))
			if self.status == "Active":
				self.validate_activation_requirements()
			return

		previous = self.get_doc_before_save()
		if not previous or previous.status == self.status:
			return

		if self.status not in STATUS_TRANSITIONS.get(previous.status, set()):
			frappe.throw(
				_("OKR Plan status cannot move from {0} to {1}.").format(previous.status, self.status)
			)

		if self.status == "Active":
			self.validate_activation_requirements()

	def validate_activation_requirements(self) -> None:
		if self.status != "Active":
			return
		ensure_required_link(self.financial_year, "Financial Year")
		ensure_required_link(self.plan_name, "Plan Name")
		ensure_required_link(self.company, "Organization")
		ensure_required_link(self.owner_user, "Plan Admin")

	def validate_locked_fields(self) -> None:
		if self.is_new():
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		if previous.status != "Draft":
			locked_fields = LOCKED_AFTER_ACTIVE_FIELDS
			if previous.status == "Active":
				locked_fields = tuple(
					fieldname for fieldname in locked_fields
					if fieldname not in {"financial_year", "sprint_frequency"}
				)
			self.validate_fields_unchanged(previous, locked_fields)

	def validate_fields_unchanged(self, previous: Document, fieldnames: tuple[str, ...]) -> None:
		for fieldname in fieldnames:
			previous_value = previous.get(fieldname)
			current_value = self.get(fieldname)
			if fieldname == "planned_activation_date" and previous_value and current_value:
				previous_value = getdate(previous_value)
				current_value = getdate(current_value)
			if previous_value != current_value:
				label = self.meta.get_label(fieldname) or fieldname
				frappe.throw(_("{0} cannot be changed after an OKR Plan becomes Active.").format(label))

	def preserve_system_calculated_progress(self) -> None:
		if self.is_new():
			self.progress = 0
			return

		self.progress = flt(self.get_db_value("progress"))

	def validate_no_dependents_before_delete(self) -> None:
		if frappe.db.exists("OKR Objective", {"parent_plan": self.name}):
			frappe.throw(_("OKR Plan cannot be deleted because dependent OKR Objectives exist."))


def activate_plan_hierarchy(plan_name: str) -> None:
	"""Activate Draft Objectives/KRs through document saves so validation and hooks run."""
	for objective_name in frappe.get_all(
		"OKR Objective", filters={"parent_plan": plan_name, "status": "Draft"}, pluck="name"
	):
		objective = frappe.get_doc("OKR Objective", objective_name)
		objective.status = "Active"
		objective.flags.ignore_permissions = True
		objective.save()

	active_objectives = frappe.get_all(
		"OKR Objective", filters={"parent_plan": plan_name, "status": "Active"}, pluck="name"
	)
	if not active_objectives:
		return
	for key_result_name in frappe.get_all(
		"OKR Key Result",
		filters={
			"parent_plan": plan_name,
			"objective": ["in", active_objectives],
			"status": ["in", ["Draft", "Planned"]],
		},
		pluck="name",
	):
		key_result = frappe.get_doc("OKR Key Result", key_result_name)
		key_result.status = "Active"
		key_result.flags.ignore_permissions = True
		key_result.save()


def _fiscal_year_dates(financial_year: str) -> tuple:
	fiscal_year_doc = frappe.db.get_value(
		"Fiscal Year", financial_year, ["year_start_date", "year_end_date"], as_dict=True
	)
	if not fiscal_year_doc or not fiscal_year_doc.year_start_date or not fiscal_year_doc.year_end_date:
		frappe.throw(_("Financial Year must have a start date and end date."))
	return getdate(fiscal_year_doc.year_start_date), getdate(fiscal_year_doc.year_end_date)


def get_plan_timeline(plan: Document | str) -> tuple:
	plan = frappe.get_doc("OKR Plan", plan) if isinstance(plan, str) else plan
	return _fiscal_year_dates(plan.financial_year)


def get_derived_periods(plan: Document | str) -> list[dict]:
	plan = frappe.get_doc("OKR Plan", plan) if isinstance(plan, str) else plan
	start, fiscal_end = _fiscal_year_dates(plan.financial_year)
	step = 1 if plan.sprint_frequency == "Monthly" else 3
	periods = []
	cursor = start
	index = 1
	while cursor <= fiscal_end:
		end = min(getdate(add_months(cursor, step)) - timedelta(days=1), fiscal_end)
		label = cursor.strftime("%B") if step == 1 else f"Q{index}"
		periods.append({"label": label, "start_date": cursor, "end_date": end})
		cursor = getdate(add_months(cursor, step))
		index += 1
	return periods


def get_period_label(item_date, plan: Document | str) -> str:
	"""Return the derived fiscal period containing item_date, or an empty label."""
	if not item_date:
		return ""

	item_date = getdate(item_date)
	for period in get_derived_periods(plan):
		if getdate(period["start_date"]) <= item_date <= getdate(period["end_date"]):
			return period["label"]
	return ""


@frappe.whitelist()
def get_plan_context(plan_name: str) -> dict:
	if frappe.session.user != "Administrator":
		frappe.throw(_("Only Administrator can access OKR Plan context."), frappe.PermissionError)
	plan = frappe.get_doc("OKR Plan", plan_name)
	start_date, end_date = get_plan_timeline(plan)
	members = [
		{
			"user": row.member_user,
			"full_name": frappe.db.get_value("User", row.member_user, "full_name") or row.member_user,
			"role": row.role,
		}
		for row in (plan.members or [])
	]
	return {
		"parent_plan": plan.name,
		"plan_name": plan.plan_name,
		"description": plan.description,
		"financial_year": plan.financial_year,
		"company": plan.company,
		"plan_owner": plan.owner_user,
		"status": plan.status,
		"planned_activation_date": plan.planned_activation_date,
		"sprint_frequency": plan.sprint_frequency,
		"start_date": start_date,
		"end_date": end_date,
		"periods": get_derived_periods(plan),
		"members": members,
	}
