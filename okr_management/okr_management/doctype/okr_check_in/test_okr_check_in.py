from __future__ import annotations

from unittest.mock import patch

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
        group = frappe.get_doc({"doctype": "Group", "group_name": "Check In Group " + frappe.generate_hash(length=8), "company": company}).insert(ignore_permissions=True)
        objective=frappe.get_doc({"doctype":"OKR Objective","group":group.name,"objective_title":"CI Objective "+frappe.generate_hash(length=6),"parent_plan":self.plan.name,"level":"Department","level_details":department,"department":department,"owner_user":"Administrator","status":"Draft"}).insert(ignore_permissions=True)
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

    def test_latest_checkin_updates_only_its_action_and_rolls_up_hierarchy(self):
        self.activate()
        other = frappe.copy_doc(self.action)
        other.action_item_title = "Other Action " + frappe.generate_hash(length=6)
        other.insert(ignore_permissions=True)

        for value in (10, 20, 30):
            self.checkin(value)

        self.action.reload()
        other.reload()
        self.kr.reload()
        objective = frappe.get_doc("OKR Objective", self.kr.objective)
        self.plan.reload()
        self.assertEqual(self.action.progress, 30)
        self.assertEqual(other.progress, 0)
        self.assertEqual(self.kr.target_progress, 15)
        self.assertEqual(objective.progress, 15)
        self.assertEqual(self.plan.progress, 15)

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

    def test_done_sets_and_preserves_completion_date(self):
        self.activate()
        frappe.set_user(self.employee_user)
        frappe.get_doc({
            "doctype": "OKR Check In",
            "action_item": self.action.name,
            "current_value": 100,
            "achievements": "Completed",
            "action_status": "Done",
        }).insert(ignore_permissions=True)
        self.action.reload()
        self.assertEqual(self.action.status, "Done")
        self.assertIsNotNone(self.action.completion_date)

        original_completion_date = "2026-01-15"
        frappe.db.set_value(
            "OKR Action Item", self.action.name, "completion_date", original_completion_date
        )
        frappe.get_doc({
            "doctype": "OKR Check In",
            "action_item": self.action.name,
            "current_value": 100,
            "achievements": "Completion confirmed",
            "action_status": "Done",
        }).insert(ignore_permissions=True)
        self.action.reload()
        self.assertEqual(str(self.action.completion_date), original_completion_date)

    def test_unauthorized_context_does_not_reveal_action_item_existence(self):
        self.activate()
        frappe.set_user("Guest")
        messages = []
        for action_item in (self.action.name, "MISSING-OKR-ACTION-ITEM"):
            with self.assertRaises(frappe.PermissionError) as error:
                from okr_management.okr_management.doctype.okr_check_in.okr_check_in import (
                    get_action_item_context,
                )

                get_action_item_context(action_item)
            messages.append(str(error.exception))
        self.assertEqual(messages[0], messages[1])
    def test_submitted_checkin_is_read_only(self):
        self.activate(); checkin=self.checkin(); checkin.achievements="Changed"
        self.assertRaises(frappe.ValidationError,checkin.save)

    def test_okr_user_cannot_delete_submitted_checkin(self):
        self.activate()
        checkin = self.checkin()
        self.assertRaises(frappe.ValidationError, checkin.delete, ignore_permissions=True)

    def test_administrator_can_delete_submitted_checkin(self):
        self.activate()
        checkin = self.checkin()
        frappe.set_user("Administrator")
        checkin.delete()
        self.assertFalse(frappe.db.exists("OKR Check In", checkin.name))

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

    def get_action_item_context(self):
        from okr_management.okr_management.doctype.okr_check_in.okr_check_in import (
            get_action_item_context,
        )

        frappe.set_user(self.employee_user)
        return get_action_item_context(self.action.name)

    def test_action_item_date_context_uses_getdate(self):
        self.activate()
        frappe.db.set_value(
            "OKR Action Item",
            self.action.name,
            {"start_date": "2026-01-01", "due_date": "2026-01-03"},
        )

        context = self.get_action_item_context()

        self.assertIn("3 Days", context["timeline_preview_context"])

    def test_key_result_date_context_uses_getdate(self):
        self.activate()
        frappe.db.set_value(
            "OKR Action Item",
            self.action.name,
            {"start_date": None, "due_date": None},
        )
        frappe.db.set_value(
            "OKR Key Result",
            self.kr.name,
            {"start_date": "2026-02-01", "end_date": "2026-02-04"},
        )

        context = self.get_action_item_context()

        self.assertIn("4 Days", context["timeline_preview_context"])

    def test_plan_date_context_uses_getdate(self):
        self.activate()
        frappe.db.set_value(
            "OKR Action Item",
            self.action.name,
            {"start_date": None, "due_date": None},
        )
        frappe.db.set_value(
            "OKR Key Result",
            self.kr.name,
            {"start_date": None, "end_date": None},
        )
        plan = frappe.get_doc("OKR Plan", self.plan.name)
        plan.start_date = "2026-03-01"
        plan.end_date = "2026-03-05"
        original_get_doc = frappe.get_doc

        def get_doc(doctype, name=None, *args, **kwargs):
            if doctype == "OKR Plan" and name == plan.name:
                return plan
            if isinstance(doctype, dict):
                return original_get_doc(doctype, *args, **kwargs)
            return original_get_doc(doctype, name, *args, **kwargs)

        with patch("frappe.get_doc", side_effect=get_doc):
            context = self.get_action_item_context()

        self.assertIn("5 Days", context["timeline_preview_context"])
