from __future__ import annotations

import calendar
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, flt, getdate, today

from okr_management.utils.okr_calculations import average, recalculate_plan_progress
from okr_management.utils.okr_validations import ensure_date_range, ensure_required_link


FULLY_LOCKED_STATUSES = {"Planned", "Active", "Completed", "Closed", "Archived"}
SPRINT_NAME_LOCKED_STATUSES = {"Active", "Completed", "Closed", "Archived"}
STATUS_TRANSITIONS = {
    "Draft": {"Planned"},
    "Planned": {"Active"},
    "Active": {"Completed"},
    "Completed": {"Closed"},
    "Closed": {"Archived"},
    "Archived": set(),
}
SETUP_LOCKED_FIELDS = (
    "parent_plan",
    "financial_year",
    "company",
    "department",
    "plan_owner",
    "sprint_cycle",
    "financial_quarter",
    "sprint_month",
    "sprint_year",
    "start_date",
    "end_date",
)
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


class OKRSprint(Document):
    def before_validate(self) -> None:
        self.normalize_legacy_cycle_values()
        self.inherit_parent_plan_context()
        self.set_default_sprint_owner()
        self.calculate_cycle_dates()
        self.calculate_summary_values()

    def validate(self) -> None:
        ensure_required_link(self.parent_plan, "Parent Plan")
        ensure_required_link(self.sprint_name, "Sprint Name")
        ensure_required_link(self.sprint_owner, "Sprint Owner")
        ensure_required_link(self.sprint_cycle, "Sprint Cycle")
        ensure_required_link(self.status, "Status")
        ensure_required_link(self.start_date, "Start Date")
        ensure_required_link(self.end_date, "End Date")
        ensure_date_range(self.start_date, self.end_date, "Sprint")
        self.validate_parent_plan_dependency()
        self.validate_lifecycle()
        self.validate_cycle_fields()
        self.validate_dates_inside_parent_plan_period()
        self.validate_one_active_sprint_per_plan()
        self.validate_objective_plan_consistency()
        self.validate_locked_fields()
        self.validate_summary_fields_are_system_owned()

    def on_update(self) -> None:
        self.sync_summary_values_to_db()
        recalculate_plan_progress(self.parent_plan)

    def on_trash(self) -> None:
        self.validate_no_objectives_before_delete()

    def normalize_legacy_cycle_values(self) -> None:
        if self.sprint_cycle == "Quarterly":
            self.sprint_cycle = "Financial Quarter"
        if self.get("quarter") and not self.financial_quarter:
            self.financial_quarter = self.get("quarter")
        quarter_labels = {'Q1':'Q1 (January - March)', 'Q2':'Q2 (April - June)', 'Q3':'Q3 (July - September)', 'Q4':'Q4 (October - December)'}
        if self.financial_quarter in quarter_labels:
            self.financial_quarter = quarter_labels[self.financial_quarter]

    def inherit_parent_plan_context(self) -> None:
        if not self.parent_plan:
            return

        plan = self.get_parent_plan()
        self.financial_year = plan.financial_year
        self.company = plan.company
        self.department = ''
        self.plan_owner = plan.owner_user

    def set_default_sprint_owner(self) -> None:
        if not self.sprint_owner:
            self.sprint_owner = self.plan_owner or frappe.session.user

    def get_parent_plan(self) -> frappe._dict:
        plan = frappe.db.get_value(
            "OKR Plan",
            self.parent_plan,
            ['name', 'status', 'financial_year', 'company', 'owner_user'],
            as_dict=True,
        )
        if not plan:
            frappe.throw(_("Parent Plan {0} does not exist.").format(self.parent_plan))
        return plan

    def get_parent_plan_period(self) -> tuple[date, date]:
        if not self.financial_year:
            frappe.throw(_("Financial Year is required from the Parent Plan."))

        fiscal_year = frappe.db.get_value(
            "Fiscal Year", self.financial_year, ["year_start_date", "year_end_date"], as_dict=True
        )
        if not fiscal_year or not fiscal_year.year_start_date or not fiscal_year.year_end_date:
            frappe.throw(_("Parent Plan Financial Year must have a start date and end date."))

        return getdate(fiscal_year.year_start_date), getdate(fiscal_year.year_end_date)

    def calculate_cycle_dates(self) -> None:
        if not self.parent_plan or not self.sprint_cycle:
            return

        if self.sprint_cycle == "Financial Quarter":
            self.calculate_financial_quarter_dates()
        elif self.sprint_cycle == "Monthly":
            self.calculate_monthly_dates()

    def calculate_financial_quarter_dates(self) -> None:
        if not self.financial_quarter:
            return

        plan_start, _plan_end = self.get_parent_plan_period()
        quarter_offsets = {'Q1': 0, 'Q2': 3, 'Q3': 6, 'Q4': 9, 'Q1 (January - March)': 0, 'Q2 (April - June)': 3, 'Q3 (July - September)': 6, 'Q4 (October - December)': 9}
        if self.financial_quarter not in quarter_offsets:
            frappe.throw(_("Financial Quarter must be Q1 (January - March), Q2 (April - June), Q3 (July - September), or Q4 (October - December)."))

        start = add_months(plan_start, quarter_offsets[self.financial_quarter])
        end = add_days(add_months(start, 3), -1)
        self.start_date = start
        self.end_date = end

    def calculate_monthly_dates(self) -> None:
        if not self.sprint_month:
            return

        month_number = MONTHS.get(self.sprint_month)
        if not month_number:
            frappe.throw(_("Month must be a valid month name."))

        self.sprint_year = self.get_financial_year_for_month(month_number)
        year = int(self.sprint_year)
        last_day = calendar.monthrange(year, month_number)[1]
        self.start_date = date(year, month_number, 1)
        self.end_date = date(year, month_number, last_day)

    def get_financial_year_for_month(self, month_number: int) -> int:
        plan_start, _plan_end = self.get_parent_plan_period()
        return plan_start.year if month_number >= plan_start.month else plan_start.year + 1

    def calculate_summary_values(self) -> None:
        if self.is_new() or not self.name:
            self.progress = 0
            self.objective_count = 0
            return

        objectives = frappe.get_all(
            "OKR Objective",
            filters={"sprint": self.name},
            fields=["name", "progress"],
        )
        self.objective_count = len(objectives)
        self.progress = average([objective.get("progress") for objective in objectives])

    def sync_summary_values_to_db(self) -> None:
        if self.is_new() or not self.name:
            return

        values = {
            "progress": flt(self.progress),
            "objective_count": int(self.objective_count or 0),
        }
        frappe.db.set_value("OKR Sprint", self.name, values, update_modified=False)

    def validate_parent_plan_dependency(self) -> None:
        self.get_parent_plan()

    def validate_lifecycle(self) -> None:
        if self.is_new():
            if self.status != "Draft":
                frappe.throw(_("New OKR Sprints must start in Draft status."))
            return

        previous = self.get_doc_before_save()
        if not previous or previous.status == self.status:
            return

        self.validate_lifecycle_actor(previous.status, self.status)
        if self.status not in STATUS_TRANSITIONS.get(previous.status, set()):
            frappe.throw(_("OKR Sprint status cannot move from {0} to {1}.").format(previous.status, self.status))

        if previous.status == "Planned" and self.status == "Active":
            self.validate_activation_window()
        elif previous.status == "Active" and self.status == "Completed":
            self.validate_completion_requirements()
        elif previous.status == "Completed" and self.status == "Closed":
            self.validate_closing_requirements()
        elif previous.status == "Closed" and self.status == "Archived":
            self.validate_archive_requirements()

    def validate_lifecycle_actor(self, previous_status: str, next_status: str) -> None:
        if self.is_okr_admin():
            return

        if next_status in {"Closed", "Archived"}:
            allowed = self.is_plan_owner()
        else:
            allowed = self.is_plan_owner() or self.is_okr_manager()

        if not allowed:
            frappe.throw(_("You are not allowed to move OKR Sprint from {0} to {1}.").format(previous_status, next_status))

    def is_okr_admin(self) -> bool:
        return frappe.session.user == "Administrator" or "OKR Admin" in frappe.get_roles(frappe.session.user)

    def is_okr_manager(self) -> bool:
        return "OKR Manager" in frappe.get_roles(frappe.session.user)

    def is_plan_owner(self) -> bool:
        return bool(self.plan_owner and self.plan_owner == frappe.session.user)

    def validate_cycle_fields(self) -> None:
        if self.sprint_cycle == "Financial Quarter":
            ensure_required_link(self.financial_quarter, "Financial Quarter")
        elif self.sprint_cycle == "Monthly":
            ensure_required_link(self.sprint_month, "Month")
            if not self.sprint_year:
                frappe.throw(_("Year is required for Monthly Sprint Cycle."))
        elif self.sprint_cycle == "Custom Date Range":
            ensure_required_link(self.start_date, "Start Date")
            ensure_required_link(self.end_date, "End Date")
        else:
            frappe.throw(_("Sprint Cycle must be Monthly, Financial Quarter, or Custom Date Range."))

    def validate_dates_inside_parent_plan_period(self) -> None:
        plan_start, plan_end = self.get_parent_plan_period()
        start = getdate(self.start_date)
        end = getdate(self.end_date)
        if start < plan_start or end > plan_end:
            frappe.throw(_("Sprint dates must stay within the Parent Plan Financial Year."))

    def validate_activation_window(self) -> None:
        current_date = getdate(today())
        if current_date < getdate(self.start_date) or current_date > getdate(self.end_date):
            frappe.throw(_("OKR Sprint cannot be activated outside its configured date range."))

    def validate_one_active_sprint_per_plan(self) -> None:
        if self.status != "Active":
            return

        filters: dict[str, Any] = {"parent_plan": self.parent_plan, "status": "Active"}
        if not self.is_new():
            filters["name"] = ["!=", self.name]
        if frappe.db.exists("OKR Sprint", filters):
            frappe.throw(_("Only one OKR Sprint may be Active within a Parent Plan."))

    def validate_completion_requirements(self) -> None:
        if frappe.db.exists("OKR Objective", {"sprint": self.name, "status": ["in", ["Active", "At Risk"]]}):
            frappe.throw(_("OKR Sprint cannot be Completed while active Objectives exist."))

    def validate_closing_requirements(self) -> None:
        if frappe.db.exists("OKR Objective", {"sprint": self.name, "status": ["in", ["Active", "At Risk"]]}):
            frappe.throw(_("OKR Sprint cannot be Closed while active Objectives exist."))

    def validate_archive_requirements(self) -> None:
        if self.status != "Archived":
            return
        self.validate_closing_requirements()

    def validate_objective_plan_consistency(self) -> None:
        if self.is_new() or not self.name:
            return
        if frappe.db.exists("OKR Objective", {"sprint": self.name, "parent_plan": ["!=", self.parent_plan]}):
            frappe.throw(_("Sprint cannot have Objectives from another Parent Plan."))

    def validate_locked_fields(self) -> None:
        if self.is_new():
            return

        previous = self.get_doc_before_save()
        if not previous:
            return

        if previous.status in FULLY_LOCKED_STATUSES or self.has_objectives():
            self.validate_fields_unchanged(previous, SETUP_LOCKED_FIELDS)

        if previous.status in SPRINT_NAME_LOCKED_STATUSES:
            self.validate_fields_unchanged(previous, ("sprint_name", "sprint_owner"))

    def validate_fields_unchanged(self, previous: Document, fieldnames: tuple[str, ...]) -> None:
        for fieldname in fieldnames:
            if previous.get(fieldname) != self.get(fieldname):
                label = self.meta.get_label(fieldname) or fieldname
                frappe.throw(_("{0} cannot be changed after an OKR Sprint is locked.").format(label))

    def validate_summary_fields_are_system_owned(self) -> None:
        if self.is_new():
            return

        expected_progress = flt(self.progress)
        expected_count = int(self.objective_count or 0)
        db_progress = flt(self.get_db_value("progress"))
        db_count = int(self.get_db_value("objective_count") or 0)
        if self.has_objectives():
            return
        if expected_progress != db_progress or expected_count != db_count:
            frappe.throw(_("Sprint Progress and Objective Count are system calculated."))

    def has_objectives(self) -> bool:
        return bool(not self.is_new() and self.name and frappe.db.exists("OKR Objective", {"sprint": self.name}))

    def validate_no_objectives_before_delete(self) -> None:
        if self.has_objectives():
            frappe.throw(_("OKR Sprint cannot be deleted because dependent Objectives exist."))
