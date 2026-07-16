from __future__ import annotations

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today


class TestOKRKeyResultPhase4(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.db.get_value("Company", {}, "name")
        if not self.company:
            self.skipTest("No Company exists on this site.")
        self.fiscal_year = self.ensure_current_fiscal_year()
        self.disabled_workflows = []
        self.disable_okr_workflows_for_tests()
        self.cleanup_records()
        self.plan = self.make_active_plan()
        self.sprint = self.make_active_sprint(self.plan)
        self.objective = self.make_active_objective(self.sprint)

    def tearDown(self):
        frappe.set_user("Administrator")
        self.cleanup_records()
        self.restore_okr_workflows_after_tests()

    def disable_okr_workflows_for_tests(self):
        self.disabled_workflows = frappe.get_all(
            "Workflow",
            filters={"document_type": ["in", ["OKR Objective", "OKR Key Result"]], "is_active": 1},
            pluck="name",
        )
        for workflow in self.disabled_workflows:
            frappe.db.set_value("Workflow", workflow, "is_active", 0, update_modified=False)

    def restore_okr_workflows_after_tests(self):
        for workflow in getattr(self, "disabled_workflows", []):
            frappe.db.set_value("Workflow", workflow, "is_active", 1, update_modified=False)

    def cleanup_records(self):
        frappe.db.delete("OKR Check In", {"key_result": ["like", "OKR-KR-%"]})
        frappe.db.delete("OKR Action Item", {"action_item_title": ["like", "Phase 4 KR%"]})
        frappe.db.delete("OKR Key Result", {"key_result_title": ["like", "Phase 4 KR%"]})
        frappe.db.delete("OKR Objective", {"objective_title": ["like", "Phase 4 KR%"]})
        frappe.db.delete("OKR Plan", {"plan_name": ["like", "Phase 4 KR%"]})
        frappe.db.delete("OKR Plan", {"plan_name": ["like", "Phase 4 KR%"]})

    def ensure_current_fiscal_year(self):
        current_date = getdate(today())
        existing_fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            {"year_start_date": ["<=", current_date], "year_end_date": [">=", current_date]},
            "name",
        )
        if existing_fiscal_year:
            return existing_fiscal_year
        fiscal_year_name = f"Phase 4 KR FY {current_date.year}"
        return frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": fiscal_year_name,
            "year_start_date": date(current_date.year, 1, 1),
            "year_end_date": date(current_date.year, 12, 31),
        }).insert(ignore_permissions=True).name

    def make_active_plan(self):
        plan = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": "Phase 4 KR Plan " + frappe.generate_hash(length=6),
            "financial_year": self.fiscal_year,
            "company": self.company,
            "owner_user": "Administrator",
            "status": "Draft",
        }).insert(ignore_permissions=True)
        plan.status = "Active"
        plan.save(ignore_permissions=True)
        return plan

    def make_active_sprint(self, plan):
        sprint = frappe.get_doc({
            "doctype": "OKR Plan",
            "parent_plan": plan.name,
            "plan_name": "Phase 4 KR Sprint " + frappe.generate_hash(length=6),
            "plan_owner": "Administrator",
            "sprint_cycle": "Custom Date Range",
            "start_date": add_days(today(), -2),
            "end_date": add_days(today(), 2),
            "status": "Draft",
        }).insert(ignore_permissions=True)
        sprint.reload()
        sprint.status = "Planned"
        sprint.save(ignore_permissions=True)
        sprint.status = "Active"
        sprint.save(ignore_permissions=True)
        return sprint

    def make_active_objective(self, sprint):
        objective = frappe.get_doc({
            "doctype": "OKR Objective",
            "objective_title": "Phase 4 KR Objective " + frappe.generate_hash(length=6),
            "sprint": sprint.name,
            "parent_plan": sprint.parent_plan,
            "financial_year": sprint.financial_year,
            "company": sprint.company,
            "department": sprint.department,
            "plan_owner": sprint.plan_owner,
            "plan_owner": sprint.plan_owner,
            "level": "Organization",
            "priority": "High",
            "owner_user": "Administrator",
            "start_date": sprint.start_date,
            "end_date": sprint.end_date,
            "status": "Active",
            "progress": 0,
            "key_result_count": 0,
        })
        objective.db_insert()
        return objective

    def make_key_result(self, **overrides):
        doc = frappe.get_doc({
            "doctype": "OKR Key Result",
            "key_result_title": overrides.pop("key_result_title", "Phase 4 KR " + frappe.generate_hash(length=6)),
            "objective": overrides.pop("objective", self.objective.name),
            "owner_user": overrides.pop("owner_user", "Administrator"),
            "calculation_mode": overrides.pop("calculation_mode", "Manual"),
            "metric_type": overrides.pop("metric_type", "Number"),
            "metric_direction": overrides.pop("metric_direction", "Increase"),
            "baseline_value": overrides.pop("baseline_value", 0),
            "current_value": overrides.pop("current_value", 25),
            "target_value": overrides.pop("target_value", 100),
            "status": overrides.pop("status", "Draft"),
            **overrides,
        })
        return doc.insert(ignore_permissions=True)

    def test_inherits_objective_context_and_dates(self):
        kr = self.make_key_result(metric_type="Currency")
        company_currency = frappe.db.get_value("Company", self.company, "default_currency")
        self.assertEqual(kr.parent_plan, self.plan.name)
        self.assertEqual(kr.parent_plan, self.sprint.name)
        self.assertEqual(kr.financial_year, self.plan.financial_year)
        self.assertEqual(kr.company, self.company)
        self.assertEqual(kr.plan_owner, self.plan.owner_user)
        self.assertEqual(kr.plan_owner, self.sprint.plan_owner)
        self.assertEqual(kr.objective_owner, self.objective.owner_user)
        self.assertEqual(getdate(kr.start_date), getdate(self.objective.start_date))
        self.assertEqual(getdate(kr.end_date), getdate(self.objective.end_date))
        self.assertEqual(kr.currency, company_currency)

    def test_manual_mode_calculates_progress_and_score(self):
        kr = self.make_key_result(current_value=40, target_value=100)
        self.assertEqual(kr.target_progress, 40)
        self.assertEqual(kr.score, kr.target_progress)
        self.assertEqual(kr.status, "Draft")

    def test_decrease_direction_calculates_progress(self):
        kr = self.make_key_result(baseline_value=10, current_value=6, target_value=2, metric_direction="Decrease")
        self.assertEqual(kr.target_progress, 50)

    def test_boolean_and_milestone_measurements(self):
        boolean_kr = self.make_key_result(metric_type="Boolean", current_value=1, target_value=0)
        milestone_kr = self.make_key_result(metric_type="Milestone", milestone_status="In Progress", target_value=0)
        self.assertEqual(boolean_kr.target_progress, 100)
        self.assertEqual(milestone_kr.target_progress, 50)

    def test_action_item_based_progress_averages_action_items_without_status_change(self):
        kr = self.make_key_result(current_value=0)
        for title, progress in (("Phase 4 KR Action 1", 20), ("Phase 4 KR Action 2", 80)):
            frappe.get_doc({
                "doctype": "OKR Action Item",
                "action_item_title": title,
                "owner_user": "Administrator",
                "parent_key_result": kr.name,
                "progress": progress,
            }).insert(ignore_permissions=True)
        from okr_management.utils.okr_calculations import recalculate_key_result_progress
        recalculate_key_result_progress(kr.name)
        kr.reload()
        self.assertEqual(kr.target_progress, 50)
        self.assertEqual(kr.score, 50)
        self.assertEqual(kr.status, "Draft")

    def test_current_value_locked_when_not_manual(self):
        kr = self.make_key_result(calculation_mode="Check-in Based", current_value=0)
        kr.current_value = 25
        self.assertRaises(frappe.ValidationError, kr.save)

    def test_duplicate_title_blocked_within_same_objective(self):
        title = "Phase 4 KR Duplicate"
        self.make_key_result(key_result_title=title)
        duplicate = frappe.get_doc({
            "doctype": "OKR Key Result",
            "key_result_title": title,
            "objective": self.objective.name,
            "owner_user": "Administrator",
            "calculation_mode": "Manual",
            "metric_type": "Number",
            "baseline_value": 0,
            "current_value": 10,
            "target_value": 100,
        })
        self.assertRaises(frappe.ValidationError, duplicate.insert)

    def test_dates_must_stay_inside_objective(self):
        kr = frappe.get_doc({
            "doctype": "OKR Key Result",
            "key_result_title": "Phase 4 KR Outside Dates",
            "objective": self.objective.name,
            "owner_user": "Administrator",
            "calculation_mode": "Manual",
            "metric_type": "Number",
            "baseline_value": 0,
            "current_value": 10,
            "target_value": 100,
            "start_date": add_days(self.objective.start_date, -1),
            "end_date": self.objective.end_date,
        })
        self.assertRaises(frappe.ValidationError, kr.insert)

    def test_lifecycle_and_activation_window(self):
        kr = self.make_key_result(start_date=add_days(today(), 1), end_date=add_days(today(), 1))
        kr.status = "Active"
        self.assertRaises(frappe.ValidationError, kr.save)
        kr.reload()
        kr.status = "Planned"
        kr.save(ignore_permissions=True)
        kr.status = "Active"
        self.assertRaises(frappe.ValidationError, kr.save)

    def test_delete_blocked_when_action_items_exist(self):
        kr = self.make_key_result()
        frappe.get_doc({
            "doctype": "OKR Action Item",
            "action_item_title": "Phase 4 KR Delete Block",
            "owner_user": "Administrator",
            "parent_key_result": kr.name,
        }).insert(ignore_permissions=True)
        self.assertRaises(frappe.ValidationError, kr.delete)

    def test_rolls_up_to_objective_progress_and_count(self):
        self.make_key_result(current_value=25)
        self.make_key_result(current_value=75)
        self.objective.reload()
        self.assertEqual(self.objective.key_result_count, 2)
        self.assertEqual(self.objective.progress, 50)
