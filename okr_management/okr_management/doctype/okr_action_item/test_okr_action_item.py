from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today


class TestOKRActionItem(FrappeTestCase):
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
        self.key_result = self.make_active_key_result(self.objective)

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
        frappe.db.delete("OKR Action Item", {"parent_key_result": ["like", "Phase 5 AI%"]})
        frappe.db.delete("OKR Action Item", {"action_item_title": ["like", "Test%"]})
        frappe.db.delete("OKR Key Result", {"key_result_title": ["like", "Phase 5 AI%"]})
        frappe.db.delete("OKR Objective", {"objective_title": ["like", "Phase 5 AI%"]})
        frappe.db.delete("OKR Plan", {"plan_name": ["like", "Phase 5 AI%"]})
        frappe.db.delete("OKR Plan", {"plan_name": ["like", "Phase 5 AI%"]})

    def ensure_current_fiscal_year(self):
        current_date = getdate(today())
        existing_fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            {"year_start_date": ["<=", current_date], "year_end_date": [">=", current_date]},
            "name",
        )
        if existing_fiscal_year:
            return existing_fiscal_year
        fiscal_year_name = f"Phase 5 AI FY {current_date.year}"
        return frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": fiscal_year_name,
            "year_start_date": today(),
            "year_end_date": add_days(today(), 365),
        }).insert(ignore_permissions=True).name

    def make_active_plan(self):
        plan = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": "Phase 5 AI Plan " + frappe.generate_hash(length=6),
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
            "plan_name": "Phase 5 AI Sprint " + frappe.generate_hash(length=6),
            "plan_owner": "Administrator",
            "sprint_cycle": "Custom Date Range",
            "start_date": add_days(today(), -5),
            "end_date": add_days(today(), 5),
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
            "objective_title": "Phase 5 AI Objective " + frappe.generate_hash(length=6),
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

    def make_active_key_result(self, objective):
        kr = frappe.get_doc({
            "doctype": "OKR Key Result",
            "key_result_title": "Phase 5 AI KR " + frappe.generate_hash(length=6),
            "objective": objective.name,
            "owner_user": "Administrator",
            "calculation_mode": "Manual",
            "metric_type": "Number",
            "baseline_value": 0,
            "target_value": 100,
            "status": "Draft",
        })
        kr.insert(ignore_permissions=True)
        kr.status = "Planned"
        kr.save(ignore_permissions=True)
        kr.status = "Active"
        kr.save(ignore_permissions=True)
        return kr

    def test_inherits_context_from_key_result(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Context Action",
            "owner_user": "Administrator",
            "status": "Open",
        })
        ai.insert(ignore_permissions=True)
        
        self.assertEqual(ai.parent_key_result, kr.name)
        self.assertEqual(ai.parent_objective, kr.objective)
        self.assertEqual(ai.parent_plan, kr.parent_plan)
        self.assertEqual(ai.parent_plan, kr.parent_plan)
        self.assertEqual(ai.company, kr.company)
        self.assertEqual(ai.department, kr.department)

    def test_default_status_is_open(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Default Status",
            "owner_user": "Administrator"
        })
        ai.insert(ignore_permissions=True)
        self.assertEqual(ai.status, "Open")

    def test_lifecycle_transitions_are_unrestricted(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Lifecycle Action",
            "owner_user": "Administrator",
            "status": "Open",
        })
        ai.insert(ignore_permissions=True)
        
        # Open -> Cancelled -> In Progress (Unrestricted in Phase 2)
        ai.status = "Cancelled"
        ai.save(ignore_permissions=True)
        ai.status = "In Progress"
        ai.save(ignore_permissions=True)
        self.assertEqual(ai.status, "In Progress")

    def test_completion_date_updates(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Completion Date",
            "owner_user": "Administrator",
            "status": "Open",
        })
        ai.insert(ignore_permissions=True)
        
        ai.status = "Completed"
        ai.save(ignore_permissions=True)
        self.assertIsNotNone(ai.completion_date)

    def test_unrestricted_delete(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Delete",
            "owner_user": "Administrator",
            "status": "Completed"
        })
        ai.insert(ignore_permissions=True)
        # Should succeed because deletion is unrestricted for Phase 2
        ai.delete()

    def test_action_date_defaults_to_today(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Action Date Today",
            "owner_user": "Administrator"
        })
        ai.insert(ignore_permissions=True)
        self.assertEqual(getdate(ai.due_date), getdate(today()))

    def test_reviewer_is_optional(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parent_key_result": kr.name,
            "action_item_title": "Test Optional Reviewer",
            "owner_user": "Administrator"
        })
        # Explicitly clear reviewer if it defaulted from Key Result
        ai.reviewer = None
        ai.insert(ignore_permissions=True)
        # Should save successfully
        self.assertIsNone(ai.reviewer)
