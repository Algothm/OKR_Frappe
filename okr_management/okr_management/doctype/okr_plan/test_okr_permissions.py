from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from okr_management.hierarchy_visibility import checkin_permission, get_hierarchy_visibility_scope
from okr_management.okr_management.page.admin_workspace.admin_workspace import get_dashboard_data


class TestOKRPermissionIntegration(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.db.get_value("Company", {}, "name")
        self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
        self.fiscal_year = frappe.db.get_value(
            "Fiscal Year", {"year_start_date": ["<=", today()], "year_end_date": [">=", today()]}, "name"
        )
        self.employees = frappe.get_all("Employee", filters={"status": "Active"}, pluck="name", limit=3)
        if not all((self.company, self.department, self.fiscal_year)) or len(self.employees) < 3:
            self.skipTest("Company, Department, Fiscal Year and three active Employees are required.")
        self.users = {
            "objective": self.make_user("objective", ["Employee"]),
            "kr": self.make_user("kr", ["Employee"]),
            "action": self.make_user("action", ["Employee"]),
            "system": self.make_user("system", ["System Manager"]),
            "okr_admin": self.make_user("okr-admin", ["OKR Admin"]),
            "okr_user": self.make_user("okr-user", ["OKR User"]),
            "dual_role": self.make_user("dual-role", ["OKR Admin", "OKR User"]),
            "outsider": self.make_user("outsider", ["Employee"]),
            "plain": self.make_user("plain", []),
        }
        for employee, key in zip(self.employees, ("objective", "kr", "action")):
            frappe.db.set_value("Employee", employee, "user_id", self.users[key])
        self.make_tree()

    def tearDown(self):
        frappe.set_user("Administrator")

    def make_user(self, prefix, roles):
        email = f"okr.permission.{prefix}@example.com"
        if not frappe.db.exists("User", email):
            frappe.get_doc({
                "doctype": "User", "email": email, "first_name": "OKR", "last_name": prefix,
                "send_welcome_email": 0, "user_type": "System User",
            }).insert(ignore_permissions=True)
        user = frappe.get_doc("User", email)
        if roles:
            user.add_roles(*roles)
        return email

    def make_tree(self):
        self.plan = frappe.get_doc({
            "doctype": "OKR Plan", "plan_name": "Permission Integration",
            "financial_year": self.fiscal_year, "company": self.company,
            "owner_user": "Administrator", "status": "Active",
        }).insert(ignore_permissions=True)
        self.objective = frappe.get_doc({
            "doctype": "OKR Objective", "objective_title": "Permission Objective",
            "parent_plan": self.plan.name, "department": self.department,
            "owner_user": self.users["objective"], "status": "Active",
        }).insert(ignore_permissions=True)
        self.kr = frappe.get_doc({
            "doctype": "OKR Key Result", "key_result_title": "Permission KR",
            "objective": self.objective.name, "assignee": self.users["kr"],
            "metric_type": "Percentage", "metric_direction": "Increase", "target_value": 100,
            "end_date": self.objective.end_date, "status": "Active",
        }).insert(ignore_permissions=True)
        self.action = frappe.get_doc({
            "doctype": "OKR Action Item", "action_item_title": "Permission Action",
            "parent_key_result": self.kr.name, "assigned_to": self.employees[2],
            "due_date": self.kr.end_date,
        }).insert(ignore_permissions=True)
        self.other_action = frappe.get_doc({
            "doctype": "OKR Action Item", "action_item_title": "Other Assignee Action",
            "parent_key_result": self.kr.name, "assigned_to": self.employees[1],
            "due_date": self.kr.end_date,
        }).insert(ignore_permissions=True)

    def test_plan_and_admin_workspace_are_okr_admin_only(self):
        frappe.set_user(self.users["outsider"])
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list("OKR Plan", pluck="name")
        self.assertFalse(frappe.has_permission("OKR Plan", "read", doc=self.plan, user=self.users["outsider"]))
        with self.assertRaises(frappe.PermissionError):
            get_dashboard_data()
        from okr_management.okr_management.doctype.okr_plan.okr_plan import get_plan_context
        with self.assertRaises(frappe.PermissionError):
            get_plan_context(self.plan.name)
        frappe.set_user(self.users["okr_user"])
        self.assertIn(self.plan.name, frappe.get_list("OKR Plan", pluck="name"))
        self.assertEqual(get_plan_context(self.plan.name)["parent_plan"], self.plan.name)
        self.assertFalse(frappe.has_permission("OKR Plan", "write", doc=self.plan))
        frappe.set_user(self.users["okr_admin"])
        self.assertTrue(frappe.has_permission("OKR Plan", "read", doc=self.plan))
        self.assertTrue(get_dashboard_data())
        frappe.set_user("Administrator")
        self.assertTrue(frappe.has_permission("OKR Plan", "read", doc=self.plan))

    def test_hierarchy_scopes_match_assignment_model(self):
        objective_scope = get_hierarchy_visibility_scope(self.users["objective"])
        self.assertIn(self.objective.name, objective_scope["visible_objectives"])
        self.assertIn(self.kr.name, objective_scope["visible_key_results"])
        self.assertIn(self.action.name, objective_scope["visible_action_items"])
        kr_scope = get_hierarchy_visibility_scope(self.users["kr"])
        self.assertIn(self.kr.name, kr_scope["visible_key_results"])
        self.assertIn(self.action.name, kr_scope["visible_action_items"])
        action_scope = get_hierarchy_visibility_scope(self.users["action"])
        self.assertIn(self.action.name, action_scope["direct_action_items"])
        self.assertIn(self.action.name, action_scope["visible_action_items"])
        self.assertNotIn(self.other_action.name, action_scope["direct_action_items"])
        self.assertNotIn(self.other_action.name, action_scope["visible_action_items"])
        self.assertNotIn(self.kr.name, action_scope["owned_key_results"])

    def test_plan_membership_does_not_grant_every_objective_branch(self):
        self.plan.append("members", {"member_user": self.users["okr_user"], "role": "Plan Coordinator"})
        self.plan.save(ignore_permissions=True)
        member_scope = get_hierarchy_visibility_scope(self.users["okr_user"])
        self.assertIn(self.plan.name, member_scope["full_plan_names"])
        self.assertNotIn(self.objective.name, member_scope["visible_objectives"])
        self.assertNotIn(self.action.name, member_scope["visible_action_items"])

    def test_only_action_item_assignee_can_checkin(self):
        probe = frappe._dict(action_item=self.action.name)
        self.assertFalse(checkin_permission(probe, self.users["system"], "create"))
        self.assertFalse(checkin_permission(probe, self.users["okr_admin"], "create"))
        self.assertFalse(checkin_permission(probe, self.users["outsider"], "create"))
        self.assertTrue(checkin_permission(probe, self.users["action"], "create"))

    def test_workspace_save_allows_assignee_and_denies_overrides(self):
        from okr_management.okr_management.page.okr_workspace.okr_workspace import save_workspace_checkin

        frappe.set_user(self.users["action"])
        proof = frappe.get_doc({
            "doctype": "File",
            "file_name": "okr-checkin-proof.txt",
            "content": "proof",
            "is_private": 1,
        }).insert(ignore_permissions=True)
        assignee_result = save_workspace_checkin(
            self.action.name, 10, "Assignee check-in", attachment=proof.file_url
        )
        self.assertTrue(assignee_result.get("name"))
        self.assertEqual(assignee_result.get("checkin", {}).get("attachment"), proof.file_url)
        proof.reload()
        self.assertEqual(proof.attached_to_doctype, "OKR Check In")
        self.assertEqual(proof.attached_to_name, assignee_result.get("name"))

        from okr_management.okr_management.page.okr_workspace.okr_workspace import get_workspace_data
        frappe.set_user(self.users["objective"])
        self.assertIn(proof.file_url, str(get_workspace_data()))
        frappe.set_user(self.users["kr"])
        self.assertIn(proof.file_url, str(get_workspace_data()))
        frappe.set_user("Administrator")
        self.assertIn(proof.file_url, str(get_dashboard_data()))
        for denied_user in (self.users["system"], self.users["okr_admin"], self.users["outsider"]):
            frappe.set_user(denied_user)
            with self.assertRaises(frappe.PermissionError):
                save_workspace_checkin(self.action.name, 20, "Non-assignee must be denied")

    def test_user_execution_routes_remain_available_for_non_admin(self):
        source = Path(frappe.get_app_path("okr_management", "public", "js", "okr_management.js")).read_text()
        for slug in ("okr-objective", "okr-key-result", "okr-action-item", "okr-check-in"):
            self.assertIn(f'"{slug}"', source)
        self.assertIn("USER_OKR_LIST_SLUGS.has(first) && !okr_user", source)
        self.assertNotIn("USER_OKR_LIST_SLUGS.has(first) && !admin_user", source)

    def test_sidebar_has_exact_admin_and_user_modes(self):
        from okr_management.navigation import get_workspace_sidebar_items

        frappe.set_user(self.users["plain"])
        no_role_pages = {
            page.get("name")
            for page in get_workspace_sidebar_items().get("pages", [])
            if page.get("module") == "OKR Management"
        }
        self.assertEqual(no_role_pages, set())

        frappe.set_user(self.users["okr_user"])
        user_pages = {
            page.get("name")
            for page in get_workspace_sidebar_items().get("pages", [])
            if page.get("module") == "OKR Management"
        }
        self.assertEqual(
            user_pages,
            {"OKR Workspace", "OKR Objective Execution", "OKR Key Result Execution", "Action Item", "Check-In"},
        )

        frappe.set_user(self.users["okr_admin"])
        admin_pages = {
            page.get("name")
            for page in get_workspace_sidebar_items().get("pages", [])
            if page.get("module") == "OKR Management"
        }
        self.assertEqual(admin_pages, {"Admin Workspace", "OKR Plan Planning"})

        frappe.set_user(self.users["dual_role"])
        dual_role_pages = {
            page.get("name")
            for page in get_workspace_sidebar_items().get("pages", [])
            if page.get("module") == "OKR Management"
        }
        self.assertEqual(
            dual_role_pages,
            {
                "Admin Workspace", "OKR Plan Planning", "OKR Workspace",
                "OKR Objective Execution", "OKR Key Result Execution", "Action Item", "Check-In",
            },
        )

    def test_dual_role_workspace_includes_full_hierarchy(self):
        from okr_management.okr_management.page.okr_workspace.okr_workspace import get_workspace_data

        frappe.set_user(self.users["dual_role"])
        data = get_workspace_data(year=self.fiscal_year, owner="me")
        objectives = data.get("objectives", [])
        self.assertIn(self.objective.name, {row.name for row in objectives})
        key_results = [kr for objective in objectives for kr in objective.get("key_results", [])]
        self.assertIn(self.kr.name, {row.name for row in key_results})
        action_items = [item for kr in key_results for item in kr.get("action_items", [])]
        self.assertIn(self.action.name, {row.name for row in action_items})

    def test_all_desk_users_can_create_objectives_but_guest_cannot(self):
        for user in (self.users["okr_user"], self.users["plain"], self.users["outsider"]):
            frappe.set_user(user)
            self.assertTrue(frappe.has_permission("OKR Objective", "create"), user)
        frappe.set_user("Guest")
        self.assertFalse(frappe.has_permission("OKR Objective", "create"))

    def test_active_kr_rejected_under_draft_parent(self):
        frappe.set_user("Administrator")
        draft_plan = frappe.get_doc({
            "doctype": "OKR Plan", "plan_name": "Draft Parent",
            "financial_year": self.fiscal_year, "company": self.company,
            "owner_user": "Administrator", "status": "Draft", "planned_activation_date": today(),
        }).insert(ignore_permissions=True)
        draft_objective = frappe.get_doc({
            "doctype": "OKR Objective", "objective_title": "Draft Parent Objective",
            "parent_plan": draft_plan.name, "department": self.department,
            "owner_user": self.users["objective"], "status": "Draft",
        }).insert(ignore_permissions=True)
        invalid = frappe.get_doc({
            "doctype": "OKR Key Result", "key_result_title": "Invalid Active KR",
            "objective": draft_objective.name, "assignee": self.users["kr"],
            "metric_type": "Percentage", "metric_direction": "Increase", "target_value": 100,
            "end_date": draft_objective.end_date, "status": "Active",
        })
        with self.assertRaises(frappe.ValidationError):
            invalid.insert(ignore_permissions=True)

        # Exercise the independent Plan guard even if inconsistent legacy data
        # contains an Active Objective under a Draft Plan.
        frappe.db.set_value("OKR Objective", draft_objective.name, "status", "Active")
        invalid_plan_parent = frappe.get_doc({
            "doctype": "OKR Key Result", "key_result_title": "Invalid Draft Plan KR",
            "objective": draft_objective.name, "assignee": self.users["kr"],
            "metric_type": "Percentage", "metric_direction": "Increase", "target_value": 100,
            "end_date": draft_objective.end_date, "status": "Active",
        })
        with self.assertRaises(frappe.ValidationError):
            invalid_plan_parent.insert(ignore_permissions=True)
