from __future__ import annotations

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from okr_management.utils.okr_calculations import recalculate_objective_progress


class TestOKRObjectivePhase3(FrappeTestCase):
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
        frappe.db.delete("OKR Key Result", {"description": ["like", "Phase 3 Objective%"]})
        frappe.db.delete("OKR Objective", {"objective_title": ["like", "Phase 3 Objective%"]})
        frappe.db.delete("OKR Sprint", {"sprint_name": ["like", "Phase 3 Objective%"]})
        frappe.db.delete("OKR Plan", {"plan_name": ["like", "Phase 3 Objective%"]})

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
        fiscal_year_name = f"Phase 3 Objective FY {current_year}"
        return frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": fiscal_year_name,
            "year_start_date": date(current_year, 1, 1),
            "year_end_date": date(current_year, 12, 31),
        }).insert(ignore_permissions=True).name

    def make_plan(self, status="Active", plan_name=None):
        plan = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": plan_name or "Phase 3 Objective Plan " + frappe.generate_hash(length=6),
            "financial_year": self.fiscal_year,
            "company": self.company,
            "owner_user": "Administrator",
            "status": "Draft",
        }).insert(ignore_permissions=True)
        if status == "Active":
            plan.status = "Active"
            plan.save(ignore_permissions=True)
        return plan

    def make_sprint(self, plan=None, status="Active", sprint_name=None):
        plan = plan or self.make_plan()
        sprint = frappe.get_doc({
            "doctype": "OKR Sprint",
            "parent_plan": plan.name,
            "sprint_name": sprint_name or "Phase 3 Objective Sprint " + frappe.generate_hash(length=6),
            "sprint_owner": "Administrator",
            "sprint_cycle": "Custom Date Range",
            "start_date": add_days(today(), -2),
            "end_date": add_days(today(), 20),
            "status": "Draft",
        }).insert(ignore_permissions=True)
        if status != "Draft":
            frappe.db.set_value("OKR Sprint", sprint.name, "status", status, update_modified=False)
            sprint.reload()
        return sprint

    def make_objective(self, sprint=None, **overrides):
        sprint = sprint or self.make_sprint()
        doc = frappe.get_doc({
            "doctype": "OKR Objective",
            "objective_title": overrides.pop("objective_title", "Phase 3 Objective " + frappe.generate_hash(length=6)),
            "sprint": sprint.name,
            "level": overrides.pop("level", "Organization"),
            "priority": overrides.pop("priority", "High"),
            "owner_user": overrides.pop("owner_user", "Administrator"),
            "status": overrides.pop("status", "Draft"),
            **overrides,
        })
        return self.insert_objective_direct(doc)

    def insert_objective_direct(self, doc):
        doc.name = "Phase 3 Objective " + frappe.generate_hash(length=10)
        doc.run_method("before_validate")
        doc.run_method("validate")
        doc.db_insert()
        doc.on_update()
        return doc

    def save_objective_direct(self, doc):
        doc.load_doc_before_save()
        doc.run_method("before_validate")
        doc.run_method("validate")
        doc.db_update()
        doc.on_update()
        return doc

    def make_key_result(self, objective, progress=0, status="Active"):
        key_result = frappe.get_doc({
            "doctype": "OKR Key Result",
            "objective": objective.name,
            "description": "Phase 3 Objective Key Result " + frappe.generate_hash(length=6),
            "target_value": 100,
            "current_value": progress,
            "target_progress": progress,
            "score": progress,
            "status": status,
        })
        key_result.name = "Phase 3 Objective Key Result " + frappe.generate_hash(length=10)
        key_result.db_insert()
        recalculate_objective_progress(objective.name)
        return key_result

    def test_inherits_context_and_defaults_dates_from_sprint(self):
        sprint = self.make_sprint()
        objective = self.make_objective(sprint, description=None)
        self.assertEqual(objective.parent_plan, sprint.parent_plan)
        self.assertEqual(objective.financial_year, sprint.financial_year)
        self.assertEqual(objective.company, sprint.company)
        self.assertEqual(objective.plan_owner, sprint.plan_owner)
        self.assertEqual(objective.sprint_owner, sprint.sprint_owner)
        self.assertEqual(getdate(objective.start_date), getdate(sprint.start_date))
        self.assertEqual(getdate(objective.end_date), getdate(sprint.end_date))

    def test_objective_title_is_required_and_description_is_optional(self):
        sprint = self.make_sprint()
        objective = frappe.get_doc({
            "doctype": "OKR Objective",
            "sprint": sprint.name,
            "level": "Organization",
            "priority": "High",
            "owner_user": "Administrator",
        })
        self.assertRaises(frappe.ValidationError, objective.insert)
        self.make_objective(sprint, description=None)

    def test_dates_can_be_shorter_but_not_outside_sprint(self):
        sprint = self.make_sprint()
        objective = self.make_objective(
            sprint,
            start_date=add_days(sprint.start_date, 1),
            end_date=add_days(sprint.end_date, -1),
        )
        self.assertGreater(getdate(objective.start_date), getdate(sprint.start_date))
        outside = frappe.get_doc({
            "doctype": "OKR Objective",
            "objective_title": "Phase 3 Objective Outside Dates",
            "sprint": sprint.name,
            "level": "Organization",
            "priority": "High",
            "owner_user": "Administrator",
            "start_date": add_days(sprint.start_date, -1),
            "end_date": sprint.end_date,
        })
        self.assertRaises(frappe.ValidationError, outside.insert)

    def test_lifecycle_requires_valid_transitions_and_active_sprint(self):
        active_sprint = self.make_sprint()
        objective = self.make_objective(active_sprint)
        
        # Draft -> Active is allowed under active sprint
        objective.status = "Active"
        self.save_objective_direct(objective)

        # Transitioning back to Draft is not allowed (not in transitions)
        objective.status = "Draft"
        self.assertRaises(frappe.ValidationError, self.save_objective_direct, objective)

        # Active under a planned sprint (not active) is not allowed to become Active
        planned_sprint = self.make_sprint(status="Planned")
        draft = self.make_objective(planned_sprint, objective_title="Phase 3 Objective Planned Sprint")
        draft.status = "Active"
        self.assertRaises(frappe.ValidationError, self.save_objective_direct, draft)

    def test_duplicate_title_in_same_sprint_is_blocked(self):
        sprint = self.make_sprint()
        self.make_objective(sprint, objective_title="Phase 3 Objective Duplicate")
        duplicate = frappe.get_doc({
            "doctype": "OKR Objective",
            "objective_title": "Phase 3 Objective Duplicate",
            "sprint": sprint.name,
            "level": "Organization",
            "priority": "High",
            "owner_user": "Administrator",
        })
        self.assertRaises(frappe.ValidationError, duplicate.insert)

    def test_progress_and_key_result_count_are_calculated_without_status_change(self):
        objective = self.make_objective()
        self.make_key_result(objective, progress=25, status="Active")
        self.make_key_result(objective, progress=75, status="Achieved")
        objective.reload()
        self.assertEqual(objective.key_result_count, 2)
        self.assertEqual(objective.progress, 50)
        self.assertEqual(objective.status, "Draft")
        objective.progress = 99
        objective.key_result_count = 9
        self.save_objective_direct(objective)
        objective.reload()
        self.assertEqual(objective.key_result_count, 2)
        self.assertEqual(objective.progress, 50)
        self.assertEqual(objective.status, "Draft")

    def test_key_result_count_recalculates_after_key_result_removal(self):
        objective = self.make_objective()
        kr = self.make_key_result(objective, progress=100, status="Achieved")
        objective.reload()
        self.assertEqual(objective.key_result_count, 1)
        frappe.db.delete("OKR Key Result", {"name": kr.name})
        recalculate_objective_progress(objective.name)
        objective.reload()
        self.assertEqual(objective.key_result_count, 0)
        self.assertEqual(objective.progress, 0)

    def test_completion_requires_completed_key_results_or_manager_partial_acceptance(self):
        objective = self.make_objective()
        self.make_key_result(objective, progress=40, status="Active")
        objective.status = "Active"
        self.save_objective_direct(objective)
        objective.status = "Completed"
        self.assertRaises(frappe.ValidationError, self.save_objective_direct, objective)
        objective.reload()
        objective.status = "Completed"
        objective.partial_completion_accepted = 1
        self.save_objective_direct(objective)
        self.assertEqual(objective.status, "Completed")

    def test_setup_fields_lock_after_planned_and_delete_blocks_key_results(self):
        objective = self.make_objective()
        objective.status = "Active"
        self.save_objective_direct(objective)
        objective.start_date = add_days(objective.start_date, 1)
        self.assertRaises(frappe.ValidationError, self.save_objective_direct, objective)

        objective.reload()
        self.make_key_result(objective)
        self.assertRaises(frappe.ValidationError, objective.delete)
