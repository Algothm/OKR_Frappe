from __future__ import annotations

from datetime import timedelta
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, get_last_day, getdate

from okr_management.utils.okr_calculations import recalculate_plan_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_required_link


LOCKED_AFTER_ACTIVE_FIELDS = (
	"financial_year",
	"company",
	"owner_user",
	"sprint_frequency",
	"period_selection",
	"custom_start_date",
	"custom_end_date",
)
STATUS_TRANSITIONS = {
	"Draft": {"Active", "Archived"},
	"Active": {"Draft", "Archived"},
	"Archived": {"Draft", "Active"},
}
SPRINT_FREQUENCIES = {"Monthly", "Quarterly", "Custom"}
MONTH_ORDER = (
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
)
MONTHS = set(MONTH_ORDER)
QUARTERS = {"Q1", "Q2", "Q3", "Q4"}


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
		self.validate_sprint_configuration()
		self.validate_lifecycle()
		self.validate_locked_fields()
		self.validate_team_members()

	def validate_sprint_frequency(self) -> None:
		if self.sprint_frequency not in SPRINT_FREQUENCIES:
			frappe.throw(_("Sprint Frequency must be Monthly, Quarterly, or Custom."))

	def validate_sprint_configuration(self) -> None:
		if self.sprint_frequency == "Monthly":
			if self.period_selection not in MONTHS:
				frappe.throw(_("Period Selection must be a valid month."))
			return

		if self.sprint_frequency == "Quarterly":
			if self.period_selection not in QUARTERS:
				frappe.throw(_("Period Selection must be Q1, Q2, Q3, or Q4."))
			return

		ensure_required_link(self.custom_start_date, "Start Date")
		ensure_required_link(self.custom_end_date, "End Date")
		ensure_date_range(self.custom_start_date, self.custom_end_date, "Custom Sprint")
		fiscal_year = frappe.db.get_value(
			"Fiscal Year",
			self.financial_year,
			["year_start_date", "year_end_date"],
			as_dict=True,
		)
		if not fiscal_year or not fiscal_year.year_start_date or not fiscal_year.year_end_date:
			frappe.throw(_("Financial Year must have a start date and end date."))
		if (
			getdate(self.custom_start_date) < getdate(fiscal_year.year_start_date)
			or getdate(self.custom_end_date) > getdate(fiscal_year.year_end_date)
		):
			frappe.throw(_("Custom Sprint dates must stay within the selected Financial Year."))

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
			self.validate_fields_unchanged(previous, LOCKED_AFTER_ACTIVE_FIELDS)

	def validate_fields_unchanged(self, previous: Document, fieldnames: tuple[str, ...]) -> None:
		for fieldname in fieldnames:
			if previous.get(fieldname) != self.get(fieldname):
				label = self.meta.get_label(fieldname) or fieldname
				frappe.throw(_("{0} cannot be changed after an OKR Plan becomes Active.").format(label))

	def validate_closing_requirements(self) -> None:
		active_objective = frappe.db.exists("OKR Objective", {"parent_plan": self.name, "status": "Active"})
		if active_objective:
			frappe.throw(_("OKR Plan cannot be Closed while dependent OKR Objectives are still Active."))

	def preserve_system_calculated_progress(self) -> None:
		if self.is_new():
			self.progress = 0
			return

		self.progress = flt(self.get_db_value("progress"))

	def validate_no_dependents_before_delete(self) -> None:
		if frappe.db.exists("OKR Objective", {"parent_plan": self.name}):
			frappe.throw(_("OKR Plan cannot be deleted because dependent OKR Objectives exist."))


def get_plan_timeline(plan: Document | str) -> tuple:
	plan = frappe.get_doc("OKR Plan", plan) if isinstance(plan, str) else plan
	if plan.sprint_frequency == "Custom":
		return getdate(plan.custom_start_date), getdate(plan.custom_end_date)

	fiscal_year = frappe.db.get_value(
		"Fiscal Year", plan.financial_year, ["year_start_date", "year_end_date"], as_dict=True
	)
	if not fiscal_year:
		frappe.throw(_("Financial Year must have a start date and end date."))
	fiscal_start = getdate(fiscal_year.year_start_date)
	fiscal_end = getdate(fiscal_year.year_end_date)
	if plan.sprint_frequency == "Quarterly":
		quarter_index = int(plan.period_selection[1]) - 1
		start = getdate(add_months(fiscal_start, quarter_index * 3))
		end = min(getdate(add_months(start, 3)) - timedelta(days=1), fiscal_end)
		return start, end

	month_number = MONTH_ORDER.index(plan.period_selection) + 1
	year = fiscal_start.year if month_number >= fiscal_start.month else fiscal_start.year + 1
	start = getdate(f"{year}-{month_number:02d}-01")
	return start, min(getdate(get_last_day(start)), fiscal_end)


@frappe.whitelist()
def get_plan_context(plan_name: str) -> dict:
	plan = frappe.get_doc("OKR Plan", plan_name)
	start_date, end_date = get_plan_timeline(plan)
	return {
		"parent_plan": plan.name,
		"plan_name": plan.plan_name,
		"financial_year": plan.financial_year,
		"company": plan.company,
		"plan_owner": plan.owner_user,
		"status": plan.status,
		"period_selection": plan.period_selection,
		"sprint_frequency": plan.sprint_frequency,
		"start_date": start_date,
		"end_date": end_date,
	}

