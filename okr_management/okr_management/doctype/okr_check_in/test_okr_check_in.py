from __future__ import annotations
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

class TestOKRCheckIn(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        company=frappe.db.get_value("Company",{},"name")
        department=frappe.db.get_value("Department",{"company":company},"name")
        employee=frappe.db.get_value("Employee",{"status":"Active","user_id":["is","set"]},["name","user_id"],as_dict=True)
        fiscal_year=frappe.db.get_value("Fiscal Year",{"year_start_date":["<=",today()],"year_end_date":[">=",today()]},"name")
        if not all((company,department,employee,fiscal_year)): self.skipTest("Required ERP masters are missing.")
        fy=frappe.db.get_value("Fiscal Year",fiscal_year,["year_start_date","year_end_date"],as_dict=True)
        self.plan=frappe.get_doc({"doctype":"OKR Plan","plan_name":"CI Test "+frappe.generate_hash(length=6),"financial_year":fiscal_year,"company":company,"owner_user":"Administrator","sprint_frequency":"Monthly","planned_activation_date":fy.year_start_date,"status":"Draft"}).insert(ignore_permissions=True)
        objective=frappe.get_doc({"doctype":"OKR Objective","objective_title":"CI Objective "+frappe.generate_hash(length=6),"parent_plan":self.plan.name,"level":"Department","level_details":department,"department":department,"owner_user":"Administrator","status":"Draft"}).insert(ignore_permissions=True)
        self.kr=frappe.get_doc({"doctype":"OKR Key Result","key_result_title":"CI KR "+frappe.generate_hash(length=6),"objective":objective.name,"assignee":"Administrator","metric_type":"Number","metric_direction":"Increase","baseline_value":0,"current_value":25,"target_value":100,"end_date":objective.end_date,"status":"Draft"}).insert(ignore_permissions=True)
        self.employee_user=employee.user_id
        self.action=frappe.get_doc({"doctype":"OKR Action Item","action_item_title":"CI Action "+frappe.generate_hash(length=6),"parent_key_result":self.kr.name,"assigned_to":employee.name,"due_date":self.kr.end_date}).insert(ignore_permissions=True)

    def activate(self):
        self.plan.status="Active"; self.plan.save(ignore_permissions=True)

    def checkin(self,current_value=40):
        frappe.set_user(self.employee_user)
        return frappe.get_doc({"doctype":"OKR Check In","action_item":self.action.name,"current_value":current_value,"achievements":"Focused test","action_status":"In Progress"}).insert(ignore_permissions=True)

    def test_draft_plan_rejects_checkin(self):
        self.assertRaises(frappe.ValidationError,self.checkin)

    def test_checkin_updates_actual_metric_and_completion(self):
        self.activate(); self.checkin(60); self.action.reload(); self.kr.reload()
        self.assertEqual(self.action.progress,60)
        self.assertEqual(self.kr.target_progress,60)
        self.assertEqual(self.kr.current_value,60)

    def test_latest_flag_is_unique(self):
        self.activate(); first=self.checkin(20); second=self.checkin(40); first.reload(); second.reload()
        self.assertEqual(first.is_latest,0)
        self.assertEqual(second.is_latest,1)

    def test_submitted_checkin_is_read_only(self):
        self.activate(); checkin=self.checkin(); checkin.achievements="Changed"
        self.assertRaises(frappe.ValidationError,checkin.save)

