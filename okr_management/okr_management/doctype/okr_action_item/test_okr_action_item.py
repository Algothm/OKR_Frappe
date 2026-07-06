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
        frappe.db.delete("OKR Action Item", {"parenttype": "OKR Key Result"})
        frappe.db.delete("OKR Key Result", {"key_result_title": ["like", "Phase 5 AI%"]})
        frappe.db.delete("OKR Objective", {"objective_title": ["like", "Phase 5 AI%"]})
        frappe.db.delete("OKR Sprint", {"sprint_name": ["like", "Phase 5 AI%"]})
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
            "doctype": "OKR Sprint",
            "parent_plan": plan.name,
            "sprint_name": "Phase 5 AI Sprint " + frappe.generate_hash(length=6),
            "sprint_owner": "Administrator",
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
            "sprint_owner": sprint.sprint_owner,
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
            "calculation_mode": "Action Item Based",
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
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Context Action",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        self.assertEqual(ai.parent_key_result, kr.name)
        self.assertEqual(ai.parent_objective, kr.objective)
        self.assertEqual(ai.parent_sprint, kr.parent_sprint)
        self.assertEqual(ai.parent_plan, kr.parent_plan)
        self.assertEqual(ai.company, kr.company)
        self.assertEqual(ai.department, kr.department)

    def test_date_boundaries(self):
        kr = self.key_result
        
        # Valid Dates (inside KR dates)
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Date Bound Action",
            "owner_user": "Administrator",
            "start_date": kr.start_date,
            "due_date": kr.end_date,
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        # Start date after due date should fail
        ai_invalid_dates = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Invalid Dates",
            "owner_user": "Administrator",
            "start_date": add_days(kr.end_date, 1),
            "due_date": kr.start_date,
            "status": "Draft",
        })
        self.assertRaises(frappe.ValidationError, ai_invalid_dates.insert)
        
        # Start date before KR start date should fail
        ai_outside_kr = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Outside KR Date",
            "owner_user": "Administrator",
            "start_date": add_days(kr.start_date, -1),
            "due_date": kr.end_date,
            "status": "Draft",
        })
        self.assertRaises(frappe.ValidationError, ai_outside_kr.insert)

    def test_lifecycle_transitions(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Lifecycle Action",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        # Draft -> Planned is valid
        ai.status = "Planned"
        ai.save(ignore_permissions=True)
        
        # Planned -> Draft is invalid
        ai.status = "Draft"
        self.assertRaises(frappe.ValidationError, ai.save)
        
        ai.reload()
        # Planned -> In Progress is valid
        ai.status = "In Progress"
        ai.save(ignore_permissions=True)

    def test_parent_key_result_active_dependency(self):
        # Create a new draft KR (not Active)
        draft_kr = frappe.get_doc({
            "doctype": "OKR Key Result",
            "key_result_title": "Phase 5 AI Draft KR",
            "objective": self.objective.name,
            "owner_user": "Administrator",
            "calculation_mode": "Action Item Based",
            "metric_type": "Number",
            "baseline_value": 0,
            "target_value": 100,
            "status": "Draft",
        }).insert(ignore_permissions=True)
        
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": draft_kr.name,
            "action_item_title": "Test Dependency Action",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        ai.status = "Planned"
        ai.save(ignore_permissions=True)
        
        # Moving to In Progress under a Draft parent KR should fail
        ai.status = "In Progress"
        self.assertRaises(frappe.ValidationError, ai.save)

    def test_completion_date_immutability(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Completion Date Action",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        ai.status = "Planned"
        ai.save(ignore_permissions=True)
        ai.status = "In Progress"
        ai.save(ignore_permissions=True)
        
        # Transition to Completed should set completion_date
        ai.status = "Completed"
        ai.save(ignore_permissions=True)
        self.assertIsNotNone(ai.completion_date)
        
        comp_date = ai.completion_date
        
        # Transition back to In Progress
        ai.status = "In Progress"
        ai.save(ignore_permissions=True)
        # completion_date must remain set (immutable)
        self.assertEqual(ai.completion_date, comp_date)
        
        # Modifying completion_date as standard user should fail
        # Set a standard employee user
        frappe.set_user("test.employee.perm@example.com")
        ai.completion_date = add_days(comp_date, 1)
        self.assertRaises(frappe.ValidationError, ai.save)
        
        frappe.set_user("Administrator")

    def test_parent_closure_rule(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Closed Parent Action",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        # Close the parent Key Result
        kr.status = "Completed"
        kr.save(ignore_permissions=True)
        kr.status = "Closed"
        kr.save(ignore_permissions=True)
        
        # Updating action item under Closed parent KR should fail
        ai.status = "Planned"
        self.assertRaises(frappe.ValidationError, ai.save)

    def test_weight_sum_constraint(self):
        kr = self.key_result
        
        ai1 = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Action 1",
            "owner_user": "Administrator",
            "weight": 40,
            "status": "Draft",
        })
        ai1.insert(ignore_permissions=True)
        
        ai2 = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Action 2",
            "owner_user": "Administrator",
            "weight": 50, # 40 + 50 = 90, which is invalid
            "status": "Draft",
        })
        # Insert will validate sum
        self.assertRaises(frappe.ValidationError, ai2.insert)
        
        # Setting weight sum to exactly 100 should succeed
        ai2.weight = 60
        ai2.insert(ignore_permissions=True)

    def test_delete_restriction(self):
        kr = self.key_result
        ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Delete Action",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai.insert(ignore_permissions=True)
        
        # Can delete in Draft status
        ai.delete()
        
        # Create and transition to Planned
        ai_planned = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Test Delete Blocked",
            "owner_user": "Administrator",
            "status": "Draft",
        })
        ai_planned.insert(ignore_permissions=True)
        ai_planned.status = "Planned"
        ai_planned.save(ignore_permissions=True)
        
        # Deletion in Planned status should fail
        self.assertRaises(frappe.ValidationError, ai_planned.delete)

    def test_progress_rollup(self):
        kr = self.key_result
        
        # Create equal weight action items (weight = 0)
        ai1 = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Equal Action 1",
            "owner_user": "Administrator",
            "progress": 20,
            "status": "Draft",
        }).insert(ignore_permissions=True)
        
        ai2 = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Equal Action 2",
            "owner_user": "Administrator",
            "progress": 80,
            "status": "Draft",
        }).insert(ignore_permissions=True)
        
        # Trigger progress recalculation for the parent Key Result
        kr.reload()
        # Average is (20 + 80) / 2 = 50%
        self.assertEqual(kr.target_progress, 50)
        self.assertEqual(kr.score, 50)
        
        # Clean up equal weight items to test weighted calculation
        frappe.db.delete("OKR Action Item", {"parent": kr.name})
        
        # Create weighted action items
        ai_w1 = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Weighted Action 1",
            "owner_user": "Administrator",
            "weight": 30,
            "progress": 40,
            "status": "Draft",
        }).insert(ignore_permissions=True)
        
        ai_w2 = frappe.get_doc({
            "doctype": "OKR Action Item",
            "parenttype": "OKR Key Result",
            "parent": kr.name,
            "action_item_title": "Weighted Action 2",
            "owner_user": "Administrator",
            "weight": 70,
            "progress": 90,
            "status": "Draft",
        }).insert(ignore_permissions=True)
        
        kr.reload()
        # Weighted progress is (40 * 0.3) + (90 * 0.7) = 12 + 63 = 75%
        self.assertEqual(kr.target_progress, 75)
        self.assertEqual(kr.score, 75)
