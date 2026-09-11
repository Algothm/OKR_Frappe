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
        self.plan=frappe.get_doc({"doctype":"OKR Plan","plan_name":"CI Test "+frappe.generate_hash(length=6),"financial_year":fiscal_year,"company":company,"owner_user":"Administrator","sprint_frequency":"Monthly","planned_activation_date":today(),"status":"Draft"}).insert(ignore_permissions=True)
        objective=frappe.get_doc({"doctype":"OKR Objective","objective_title":"CI Objective "+frappe.generate_hash(length=6),"parent_plan":self.plan.name,"level":"Department","level_details":department,"department":department,"owner_user":"Administrator","status":"Draft"}).insert(ignore_permissions=True)
        self.kr=frappe.get_doc({"doctype":"OKR Key Result","key_result_title":"CI KR "+frappe.generate_hash(length=6),"objective":objective.name,"assignee":"Administrator","metric_type":"Number","metric_direction":"Increase","calculation_mode":"Automatic","baseline_value":0,"current_value":0,"target_value":100,"end_date":objective.end_date,"status":"Draft"}).insert(ignore_permissions=True)
        self.employee_user=employee.user_id
        if "OKR User" not in frappe.get_roles(self.employee_user):
            frappe.get_doc("User", self.employee_user).add_roles("OKR User")
        self.action=frappe.get_doc({"doctype":"OKR Action Item","action_item_title":"CI Action "+frappe.generate_hash(length=6),"parent_key_result":self.kr.name,"assigned_to":employee.user_id,"due_date":self.kr.end_date}).insert(ignore_permissions=True)

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

    def test_archived_action_item_still_accepts_checkin_while_plan_is_active(self):
        self.activate()
        self.action.status = "Archived"
        self.action.save(ignore_permissions=True)
        checkin = self.checkin(70)
        self.action.reload()
        self.assertEqual(checkin.progress, 70)
        self.assertEqual(self.action.status, "In Progress")

    def test_increase_goal_allows_overachievement_without_changing_target(self):
        self.activate()
        checkin = self.checkin(125)
        self.action.reload()
        self.kr.reload()
        self.assertEqual(checkin.current_value, 125)
        self.assertEqual(checkin.progress, 100)
        self.assertEqual(self.kr.current_value, 100)
        self.assertEqual(self.kr.target_value, 100)
        self.assertEqual(self.kr.target_progress, 100)

    def test_latest_flag_is_unique(self):
        self.activate(); first=self.checkin(20); second=self.checkin(40); first.reload(); second.reload()
        self.assertEqual(first.is_latest,0)
        self.assertEqual(second.is_latest,1)

    def test_selected_status_is_preserved_and_updates_action_item(self):
        self.activate()

        frappe.set_user(self.employee_user)
        on_hold = frappe.get_doc({
            "doctype": "OKR Check In",
            "action_item": self.action.name,
            "current_value": 50,
            "achievements": "Paused for a dependency",
            "action_status": "On Hold",
        }).insert(ignore_permissions=True)
        self.action.reload()
        self.assertEqual(on_hold.action_status, "On Hold")
        self.assertEqual(self.action.status, "On Hold")

        resumed = frappe.get_doc({
            "doctype": "OKR Check In",
            "action_item": self.action.name,
            "current_value": 60,
            "achievements": "Dependency cleared",
            "action_status": "In Progress",
        }).insert(ignore_permissions=True)
        self.action.reload()
        self.assertEqual(resumed.action_status, "In Progress")
        self.assertEqual(self.action.status, "In Progress")
    def test_submitted_checkin_is_read_only(self):
        self.activate(); checkin=self.checkin(); checkin.achievements="Changed"
        self.assertRaises(frappe.ValidationError,checkin.save)

    def test_stale_zero_kr_checkin_count_does_not_bypass_submitted_immutability(self):
        self.activate()
        checkin = self.checkin()
        frappe.db.set_value("OKR Key Result", self.kr.name, "checkin_count", 0)
        checkin.achievements = "Changed despite stale count"
        self.assertRaises(frappe.ValidationError, checkin.save)

    def test_checkin_date_defaults_to_today_when_not_supplied(self):
        self.activate()
        frappe.set_user(self.employee_user)
        ci = frappe.get_doc({
            "doctype": "OKR Check In",
            "action_item": self.action.name,
            "current_value": 30,
            "achievements": "Default date check",
            "action_status": "In Progress",
        }).insert(ignore_permissions=True)
        self.assertEqual(str(ci.checkin_date), today())

    def test_checkin_custom_date_persists_and_is_not_overwritten(self):
        self.activate()
        frappe.set_user(self.employee_user)
        custom_date = "2026-09-01"
        ci = frappe.get_doc({
            "doctype": "OKR Check In",
            "action_item": self.action.name,
            "current_value": 35,
            "achievements": "Custom date check",
            "action_status": "In Progress",
            "checkin_date": custom_date,
        }).insert(ignore_permissions=True)
        ci.reload()
        self.assertEqual(str(ci.checkin_date), custom_date)

    def test_save_workspace_checkin_persists_custom_date(self):
        from okr_management.okr_management.page.okr_workspace.okr_workspace import save_workspace_checkin
        self.activate()
        if "OKR User" not in frappe.get_roles(self.employee_user):
            frappe.get_doc("User", self.employee_user).add_roles("OKR User")
        frappe.set_user(self.employee_user)
        custom_date = "2026-08-25"
        res = save_workspace_checkin(
            action_item=self.action.name,
            current_value=45,
            update="Workspace custom date check",
            status="In Progress",
            checkin_date=custom_date,
        )
        ci = frappe.get_doc("OKR Check In", res["name"])
        self.assertEqual(str(ci.checkin_date), custom_date)

    def test_save_workspace_checkin_defaults_date_to_today_when_omitted(self):
        from okr_management.okr_management.page.okr_workspace.okr_workspace import save_workspace_checkin
        self.activate()
        if "OKR User" not in frappe.get_roles(self.employee_user):
            frappe.get_doc("User", self.employee_user).add_roles("OKR User")
        frappe.set_user(self.employee_user)
        res = save_workspace_checkin(
            action_item=self.action.name,
            current_value=50,
            update="Workspace default date check",
            status="In Progress",
        )
        ci = frappe.get_doc("OKR Check In", res["name"])
        self.assertEqual(str(ci.checkin_date), today())
