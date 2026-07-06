from __future__ import annotations

import calendar
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today
from okr_management.utils.okr_calculations import recalculate_sprint_progress


class TestOKRSprintPhase2(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.db.get_value("Company", {}, "name")
        if not self.company:
            self.skipTest("No Company exists on this site.")
        self.fiscal_year = self.ensure_current_fiscal_year()
        self.cleanup_records()

    def tearDown(self):
        frappe.set_user("Administrator")
        self.cleanup_records()

    def cleanup_records(self):
        frappe.db.delete("OKR Objective", {"description": ["like", "Phase 2 Sprint%"]})
        frappe.db.delete("OKR Sprint", {"sprint_name": ["like", "Phase 2 Sprint%"]})
        frappe.db.delete("OKR Plan", {"plan_name": ["like", "Phase 2 Sprint%"]})

    def ensure_current_fiscal_year(self):
        current_date = getdate(today())
        existing_fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            {
                "year_start_date": ["<=", current_date],
                "year_end_date": [">=", current_date],
            },
            "name",
        )
        if existing_fiscal_year:
            return existing_fiscal_year

        current_year = current_date.year
        fiscal_year_name = f"Phase 2 Sprint FY {current_year}"
        return frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": fiscal_year_name,
            "year_start_date": date(current_year, 1, 1),
            "year_end_date": date(current_year, 12, 31),
        }).insert(ignore_permissions=True).name

    def make_plan(self, status="Active", plan_name="Phase 2 Sprint Plan"):
        plan = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": plan_name,
            "financial_year": self.fiscal_year,
            "company": self.company,
            "owner_user": "Administrator",
            "status": "Draft",
        }).insert(ignore_permissions=True)
        if status == "Active":
            plan.status = "Active"
            plan.save(ignore_permissions=True)
        return plan

    def make_sprint(self, plan=None, **overrides):
        plan = plan or self.make_plan(plan_name="Phase 2 Sprint Plan " + frappe.generate_hash(length=6))
        doc = frappe.get_doc({
            "doctype": "OKR Sprint",
            "parent_plan": plan.name,
            "sprint_name": overrides.pop("sprint_name", "Phase 2 Sprint " + frappe.generate_hash(length=6)),
            "sprint_owner": overrides.pop("sprint_owner", "Administrator"),
            "sprint_cycle": overrides.pop("sprint_cycle", "Custom Date Range"),
            "start_date": overrides.pop("start_date", add_days(today(), -1)),
            "end_date": overrides.pop("end_date", add_days(today(), 1)),
            "status": "Draft",
            **overrides,
        })
        return doc.insert(ignore_permissions=True)

    def make_objective(self, sprint, progress=0, status="Completed"):
        objective = frappe.get_doc({
            "doctype": "OKR Objective",
            "parent_plan": sprint.parent_plan,
            "sprint": sprint.name,
            "level": "Organization",
            "company": sprint.company,
            "description": "Phase 2 Sprint Objective " + frappe.generate_hash(length=6),
            "owner_user": "Administrator",
            "status": status,
            "progress": progress,
        })
        objective.name = "Phase 2 Sprint Objective " + frappe.generate_hash(length=10)
        objective.db_insert()
        recalculate_sprint_progress(sprint.name)
        return objective

    def plan_period(self):
        fiscal_year = frappe.db.get_value(
            "Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
        )
        return getdate(fiscal_year.year_start_date), getdate(fiscal_year.year_end_date)

    def test_inherits_parent_plan_context_and_financial_quarter_dates(self):
        plan = self.make_plan()
        sprint = self.make_sprint(
            plan,
            sprint_cycle="Financial Quarter",
            financial_quarter="Q2",
            start_date=None,
            end_date=None,
        )
        plan_start, _plan_end = self.plan_period()
        self.assertEqual(sprint.financial_year, plan.financial_year)
        self.assertEqual(sprint.company, plan.company)
        self.assertEqual(sprint.department, plan.department)
        self.assertEqual(sprint.plan_owner, plan.owner_user)
        self.assertEqual(getdate(sprint.start_date), date(plan_start.year, 4, 1))
        self.assertEqual(getdate(sprint.end_date), date(plan_start.year, 6, 30))

    def test_sprint_requires_active_parent_plan(self):
        draft_plan = self.make_plan(status="Draft", plan_name="Phase 2 Sprint Draft Parent")
        sprint = frappe.get_doc({
            "doctype": "OKR Sprint",
            "parent_plan": draft_plan.name,
            "sprint_name": "Phase 2 Sprint Invalid Parent",
            "sprint_owner": "Administrator",
            "sprint_cycle": "Custom Date Range",
            "start_date": add_days(today(), -1),
            "end_date": add_days(today(), 1),
        })
        self.assertRaises(frappe.ValidationError, sprint.insert)

    def test_lifecycle_and_one_active_sprint_per_plan(self):
        plan = self.make_plan()
        sprint = self.make_sprint(plan, sprint_name="Phase 2 Sprint Active One")
        sprint.status = "Active"
        self.assertRaises(frappe.ValidationError, sprint.save)
        sprint.reload()
        sprint.status = "Planned"
        sprint.save(ignore_permissions=True)
        sprint.status = "Active"
        sprint.save(ignore_permissions=True)

        second = self.make_sprint(plan, sprint_name="Phase 2 Sprint Active Two")
        second.status = "Planned"
        second.save(ignore_permissions=True)
        second.status = "Active"
        self.assertRaises(frappe.ValidationError, second.save)

    def test_sprint_cannot_activate_outside_configured_date_range(self):
        sprint = self.make_sprint(start_date=add_days(today(), 10), end_date=add_days(today(), 20))
        sprint.status = "Planned"
        sprint.save(ignore_permissions=True)
        sprint.status = "Active"
        self.assertRaises(frappe.ValidationError, sprint.save)

    def test_monthly_cycle_uses_month_and_year(self):
        current_date = getdate(today())
        month_name = calendar.month_name[current_date.month]
        sprint = self.make_sprint(
            sprint_cycle="Monthly",
            sprint_month=month_name,
            sprint_year=current_date.year,
            start_date=None,
            end_date=None,
        )
        last_day = calendar.monthrange(current_date.year, current_date.month)[1]
        self.assertEqual(getdate(sprint.start_date), date(current_date.year, current_date.month, 1))
        self.assertEqual(getdate(sprint.end_date), date(current_date.year, current_date.month, last_day))

    def test_custom_dates_must_stay_inside_parent_period(self):
        plan_start, _plan_end = self.plan_period()
        sprint = frappe.get_doc({
            "doctype": "OKR Sprint",
            "parent_plan": self.make_plan().name,
            "sprint_name": "Phase 2 Sprint Outside Dates",
            "sprint_owner": "Administrator",
            "sprint_cycle": "Custom Date Range",
            "start_date": add_days(plan_start, -5),
            "end_date": add_days(plan_start, 5),
        })
        self.assertRaises(frappe.ValidationError, sprint.insert)

    def test_setup_fields_lock_after_planned(self):
        sprint = self.make_sprint()
        sprint.status = "Planned"
        sprint.save(ignore_permissions=True)
        sprint.start_date = add_days(sprint.start_date, 1)
        self.assertRaises(frappe.ValidationError, sprint.save)

    def test_progress_and_objective_count_are_calculated_from_objectives(self):
        sprint = self.make_sprint()
        self.make_objective(sprint, progress=25)
        self.make_objective(sprint, progress=75)
        sprint.reload()
        sprint.save(ignore_permissions=True)
        sprint.reload()
        self.assertEqual(sprint.objective_count, 2)
        self.assertEqual(sprint.progress, 50)
        sprint.progress = 99
        sprint.objective_count = 9
        sprint.save(ignore_permissions=True)
        sprint.reload()
        self.assertEqual(sprint.objective_count, 2)
        self.assertEqual(sprint.progress, 50)

    def test_delete_blocked_when_objectives_exist(self):
        sprint = self.make_sprint()
        self.make_objective(sprint)
        self.assertRaises(frappe.ValidationError, sprint.delete)
