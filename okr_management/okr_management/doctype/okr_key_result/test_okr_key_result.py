from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today
from okr_management.utils.okr_calculations import recalculate_key_result_progress

class TestOKRKeyResult(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.db.get_value("Company", {}, "name")
        self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
        self.employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
        self.fiscal_year = frappe.db.get_value("Fiscal Year", {"year_start_date": ["<=", today()], "year_end_date": [">=", today()]}, "name")
        if not all((self.company, self.department, self.employee, self.fiscal_year)):
            self.skipTest("Required ERP masters are missing.")
        fy = frappe.db.get_value("Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
        self.plan = frappe.get_doc({"doctype":"OKR Plan","plan_name":"KR Test "+frappe.generate_hash(length=6),"financial_year":self.fiscal_year,"company":self.company,"owner_user":"Administrator","sprint_frequency":"Monthly","planned_activation_date":fy.year_start_date,"status":"Draft"}).insert(ignore_permissions=True)
        self.plan.status = "Active"; self.plan.save(ignore_permissions=True)
        self.objective = frappe.get_doc({"doctype":"OKR Objective","objective_title":"KR Objective "+frappe.generate_hash(length=6),"parent_plan":self.plan.name,"level":"Department","level_details":self.department,"department":self.department,"owner_user":"Administrator","status":"Draft"}).insert(ignore_permissions=True)

    def make_kr(self, **values):
        payload={"doctype":"OKR Key Result","key_result_title":"KR Test "+frappe.generate_hash(length=6),"objective":self.objective.name,"assignee":"Administrator","metric_type":"Number","metric_direction":"Increase","calculation_mode":"Manual","baseline_value":0,"current_value":25,"target_value":100,"end_date":self.objective.end_date,"status":"Draft"}
        payload.update(values)
        return frappe.get_doc(payload).insert(ignore_permissions=True)

    def make_action(self, kr, progress=0, due_date=None):
        return frappe.get_doc({"doctype":"OKR Action Item","action_item_title":"KR Action "+frappe.generate_hash(length=6),"parent_key_result":kr.name,"assigned_to":self.employee,"due_date":due_date or kr.end_date,"progress":progress}).insert(ignore_permissions=True)

    def test_target_date_is_required_and_editable(self):
        self.assertRaises(frappe.ValidationError, self.make_kr, end_date=None)
        target=add_days(self.objective.start_date,30)
        kr=self.make_kr(end_date=target)
        self.assertEqual(getdate(kr.end_date),getdate(target))

    def test_target_date_must_stay_inside_objective(self):
        self.assertRaises(frappe.ValidationError,self.make_kr,end_date=add_days(self.objective.end_date,1))

    def test_target_date_cannot_exclude_existing_action(self):
        kr=self.make_kr(); action=self.make_action(kr)
        kr.end_date=add_days(action.due_date,-1)
        self.assertRaises(frappe.ValidationError,kr.save)

    def test_measurement_progress_increase_and_decrease(self):
        self.assertEqual(self.make_kr(current_value=40).target_progress,40)
        self.assertEqual(self.make_kr(baseline_value=10,current_value=6,target_value=2,metric_direction="Decrease").target_progress,50)

    def test_manual_metric_value_remains_authoritative_with_actions(self):
        kr=self.make_kr(current_value=25)
        self.make_action(kr,20); self.make_action(kr,80)
        recalculate_key_result_progress(kr.name); kr.reload()
        self.assertEqual(kr.target_progress,25)
        self.assertEqual(kr.current_value,25)

    def test_assignee_is_canonical_owner(self):
        kr=self.make_kr()
        self.assertEqual(kr.owner_user,kr.assignee)

