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
			"objective": self.make_user("objective", ["Employee", "Department Head", "OKR User"]),
			"kr": self.make_user("kr", ["Employee", "OKR User"]),
			"action": self.make_user("action", ["Employee", "OKR User"]),
			"system": self.make_user("system", ["System Manager"]),
			"okr_admin": self.make_user("okr-admin", ["OKR Admin"]),
			"okr_user": self.make_user("okr-user", ["OKR User"]),
			"dual_role": self.make_user("dual-role", ["OKR Admin", "OKR User"]),
			"outsider": self.make_user("outsider-no-okr", ["Employee"]),
			"plain": self.make_user("plain", []),
		}
		for employee, key in zip(self.employees, ("objective", "kr", "action"), strict=False):
			frappe.db.set_value("Employee", employee, "user_id", self.users[key])
		self.make_tree()

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_user(self, prefix, roles):
		email = f"okr.permission.{prefix}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "OKR",
					"last_name": prefix,
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		if roles:
			user.add_roles(*roles)
		return email

	def make_tree(self):
		self.plan = frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "Permission Integration",
				"financial_year": self.fiscal_year,
				"company": self.company,
				"owner_user": "Administrator",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		self.objective = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "Permission Objective",
				"parent_plan": self.plan.name,
				"department": self.department,
				"owner_user": self.users["objective"],
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		self.kr = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "Permission KR",
				"objective": self.objective.name,
				"assignee": self.users["kr"],
				"metric_type": "Percentage",
				"metric_direction": "Increase",
				"target_value": 100,
				"end_date": self.objective.end_date,
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		self.action = frappe.get_doc(
			{
				"doctype": "OKR Action Item",
				"action_item_title": "Permission Action",
				"parent_key_result": self.kr.name,
				"assigned_to": self.users["action"],
				"due_date": self.kr.end_date,
			}
		).insert(ignore_permissions=True)
		self.other_action = frappe.get_doc(
			{
				"doctype": "OKR Action Item",
				"action_item_title": "Other Assignee Action",
				"parent_key_result": self.kr.name,
				"assigned_to": self.users["kr"],
				"due_date": self.kr.end_date,
			}
		).insert(ignore_permissions=True)

	def test_plan_and_admin_workspace_are_okr_admin_only(self):
		frappe.set_user(self.users["outsider"])
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("OKR Plan", pluck="name")
		self.assertFalse(
			frappe.has_permission("OKR Plan", "read", doc=self.plan, user=self.users["outsider"])
		)
		with self.assertRaises(frappe.PermissionError):
			get_dashboard_data()
		from okr_management.okr_management.doctype.okr_plan.okr_plan import get_plan_context

		with self.assertRaises(frappe.PermissionError):
			get_plan_context(self.plan.name)
		frappe.set_user(self.users["okr_user"])
		self.assertFalse(frappe.has_permission("OKR Plan", "read", doc=self.plan))
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
		self.assertIn(self.kr.name, action_scope["visible_key_results"])
		self.assertIn(self.objective.name, action_scope["visible_objectives"])
		self.assertNotIn(self.other_action.name, action_scope["direct_action_items"])
		self.assertNotIn(self.other_action.name, action_scope["visible_action_items"])
		self.assertNotIn(self.kr.name, action_scope["owned_key_results"])

	def test_plan_membership_grants_complete_plan_tree_read_visibility(self):
		self.plan.append("members", {"member_user": self.users["okr_user"], "role": "Plan Coordinator"})
		self.plan.save(ignore_permissions=True)
		member_scope = get_hierarchy_visibility_scope(self.users["okr_user"])
		self.assertIn(self.plan.name, member_scope["full_plan_names"])
		self.assertIn(self.objective.name, member_scope["visible_objectives"])
		self.assertIn(self.kr.name, member_scope["visible_key_results"])
		self.assertIn(self.action.name, member_scope["visible_action_items"])
		self.assertFalse(member_scope["direct_action_items"])

	def test_only_action_item_assignee_can_checkin(self):
		probe = frappe._dict(action_item=self.action.name)
		self.assertFalse(checkin_permission(probe, self.users["system"], "create"))
		self.assertFalse(checkin_permission(probe, self.users["okr_admin"], "create"))
		self.assertFalse(checkin_permission(probe, self.users["outsider"], "create"))
		self.assertTrue(checkin_permission(probe, self.users["action"], "create"))

	def test_action_assignee_workspace_dropdown_and_save_flow(self):
		from okr_management.okr_management.doctype.okr_check_in.okr_check_in import (
			get_assigned_action_items,
		)
		from okr_management.okr_management.page.okr_workspace.okr_workspace import (
			get_workspace_data,
			save_workspace_checkin,
		)

		frappe.set_user(self.users["action"])
		data = get_workspace_data(plan=self.plan.name, level="", owner="me")
		objectives = data.get("objectives", [])
		self.assertIn(self.objective.name, {row.name for row in objectives})
		key_results = [kr for objective in objectives for kr in objective.get("key_results", [])]
		self.assertIn(self.kr.name, {row.name for row in key_results})
		action_items = [item for kr in key_results for item in kr.get("action_items", [])]
		self.assertIn(self.action.name, {row.name for row in action_items})
		self.assertNotIn(self.other_action.name, {row.name for row in action_items})

		dropdown = get_assigned_action_items("OKR Action Item", "", "name", 0, 20, {})
		dropdown_names = {row[0] for row in dropdown}
		self.assertIn(self.action.name, dropdown_names)
		self.assertNotIn(self.other_action.name, dropdown_names)

		frappe.set_user(self.users["action"])
		proof = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "okr-checkin-proof.txt",
				"content": "proof",
				"is_private": 1,
			}
		).insert(ignore_permissions=True)
		assignee_result = save_workspace_checkin(self.action.name, 10, "", attachment=proof.file_url)
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

	def test_sidebar_uses_native_routes_without_click_interceptor(self):
		from okr_management.navigation import get_workspace_sidebar_items

		hooks_source = Path(frappe.get_app_path("okr_management", "hooks.py")).read_text()
		self.assertNotIn("okr_navigation_v3.js", hooks_source)
		global_source = Path(
			frappe.get_app_path("okr_management", "public", "js", "okr_management.js")
		).read_text()
		self.assertNotIn("frappe.re_route", global_source)
		self.assertNotIn("enforce_okr_route_access", global_source)

		frappe.set_user(self.users["dual_role"])
		pages = {
			page.get("name"): page.get("route")
			for page in get_workspace_sidebar_items().get("pages", [])
			if page.get("module") == "OKR Management"
		}
		self.assertEqual(pages["OKR Admin Workspace Sidebar"], "admin-workspace")
		self.assertEqual(pages["OKR Plan Planning"], "okr-plan")
		self.assertEqual(pages["OKR Workspace Sidebar"], "okr-workspace")
		self.assertEqual(pages["OKR Objective Execution"], "okr-objective")
		self.assertEqual(pages["OKR Key Result Execution"], "okr-key-result")
		self.assertEqual(pages["Action Item"], "okr-action-item")
		self.assertEqual(pages["Check-In"], "okr-check-in")

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
			{
				"OKR Workspace Sidebar",
				"OKR Objective Execution",
				"OKR Key Result Execution",
				"Action Item",
				"Check-In",
			},
		)

		frappe.set_user(self.users["okr_admin"])
		admin_pages = {
			page.get("name")
			for page in get_workspace_sidebar_items().get("pages", [])
			if page.get("module") == "OKR Management"
		}
		self.assertEqual(admin_pages, {"OKR Admin Workspace Sidebar", "OKR Plan Planning"})

		frappe.set_user(self.users["dual_role"])
		dual_role_pages = {
			page.get("name")
			for page in get_workspace_sidebar_items().get("pages", [])
			if page.get("module") == "OKR Management"
		}
		self.assertEqual(
			dual_role_pages,
			{
				"OKR Admin Workspace Sidebar",
				"OKR Plan Planning",
				"OKR Workspace Sidebar",
				"OKR Objective Execution",
				"OKR Key Result Execution",
				"Action Item",
				"Check-In",
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
		frappe.set_user(self.users["okr_user"])
		self.assertTrue(frappe.has_permission("OKR Objective", "create"))
		for user in (self.users["plain"], self.users["outsider"], "Guest"):
			frappe.set_user(user)
			self.assertFalse(frappe.has_permission("OKR Objective", "create"), user)

	def test_objective_owner_can_activate_under_active_plan(self):
		frappe.set_user("Administrator")
		objective = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "Owner Activation " + frappe.generate_hash(length=6),
				"parent_plan": self.plan.name,
				"department": self.department,
				"owner_user": self.users["objective"],
				"status": "Draft",
			}
		).insert(ignore_permissions=True)

		frappe.set_user(self.users["objective"])
		objective.status = "Active"
		objective.save()
		self.assertEqual(objective.status, "Active")

	def test_department_objective_permissions_and_checkins(self):
		from okr_management.okr_management.doctype.okr_check_in.okr_check_in import (
			get_assigned_action_items,
		)
		from okr_management.okr_management.page.okr_workspace.okr_workspace import (
			save_workspace_checkin,
		)

		definitions = (
			(
				"Department",
				{
					"department": self.department,
					"owner_user": self.users["objective"],
				},
			),
		)
		records = []
		frappe.set_user("Administrator")
		for index, (level, extra) in enumerate(definitions, start=1):
			objective_values = {
				"doctype": "OKR Objective",
				"objective_title": f"{level} E2E Objective {frappe.generate_hash(length=6)}",
				"parent_plan": self.plan.name,
				"level": level,
				"owner_user": self.users["objective"],
				"status": "Active",
				**extra,
			}
			objective = frappe.get_doc(objective_values).insert(ignore_permissions=True)
			key_result = frappe.get_doc(
				{
					"doctype": "OKR Key Result",
					"key_result_title": f"{level} E2E KR {frappe.generate_hash(length=6)}",
					"objective": objective.name,
					"assignee": self.users["kr"],
					"metric_type": "Percentage",
					"metric_direction": "Increase",
					"baseline_value": 0,
					"current_value": 0,
					"target_value": 100,
					"end_date": objective.end_date,
					"status": "Active",
				}
			).insert(ignore_permissions=True)
			action = frappe.get_doc(
				{
					"doctype": "OKR Action Item",
					"action_item_title": f"{level} E2E Action {frappe.generate_hash(length=6)}",
					"parent_key_result": key_result.name,
					"assigned_to": self.users["action"],
					"due_date": key_result.end_date,
				}
			).insert(ignore_permissions=True)
			records.append((level, objective, key_result, action, index * 10))

		objective_scope = get_hierarchy_visibility_scope(self.users["objective"])
		kr_scope = get_hierarchy_visibility_scope(self.users["kr"])
		action_scope = get_hierarchy_visibility_scope(self.users["action"])
		outsider_scope = get_hierarchy_visibility_scope(self.users["outsider"])

		for level, objective, key_result, action, value in records:
			with self.subTest(level=level):
				self.assertIn(objective.name, objective_scope["visible_objectives"])
				self.assertIn(key_result.name, kr_scope["visible_key_results"])
				self.assertIn(action.name, action_scope["direct_action_items"])
				self.assertIn(key_result.name, action_scope["visible_key_results"])
				self.assertIn(objective.name, action_scope["visible_objectives"])
				self.assertNotIn(objective.name, outsider_scope["visible_objectives"])

				frappe.set_user(self.users["action"])
				self.assertIn(objective.name, frappe.get_list("OKR Objective", pluck="name"))
				self.assertIn(key_result.name, frappe.get_list("OKR Key Result", pluck="name"))
				self.assertIn(action.name, frappe.get_list("OKR Action Item", pluck="name"))
				result = save_workspace_checkin(action.name, value, f"{level} assigned-user check-in")
				self.assertTrue(result.get("name"))
				action.reload()
				key_result.reload()
				self.assertEqual(action.progress, value)
				self.assertEqual(key_result.current_value, value)

				frappe.set_user(self.users["outsider"])
				with self.assertRaises(frappe.PermissionError):
					save_workspace_checkin(action.name, value + 1, f"{level} outsider check-in")

		frappe.set_user(self.users["action"])
		dropdown_names = {
			row[0] for row in get_assigned_action_items("OKR Action Item", "", "name", 0, 100, {})
		}
		self.assertTrue({row[3].name for row in records}.issubset(dropdown_names))

		checkins = frappe.get_all(
			"OKR Check In",
			filters={"action_item": ["in", [row[3].name for row in records]]},
			pluck="action_item",
		)
		self.assertEqual(set(checkins), {row[3].name for row in records})

	def test_active_kr_rejected_under_draft_parent(self):
		frappe.set_user("Administrator")
		draft_plan = frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "Draft Parent",
				"financial_year": self.fiscal_year,
				"company": self.company,
				"owner_user": "Administrator",
				"status": "Draft",
				"planned_activation_date": today(),
			}
		).insert(ignore_permissions=True)
		draft_objective = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "Draft Parent Objective",
				"parent_plan": draft_plan.name,
				"department": self.department,
				"owner_user": self.users["objective"],
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		invalid = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "Invalid Active KR",
				"objective": draft_objective.name,
				"assignee": self.users["kr"],
				"metric_type": "Percentage",
				"metric_direction": "Increase",
				"target_value": 100,
				"end_date": draft_objective.end_date,
				"status": "Active",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			invalid.insert(ignore_permissions=True)

		# Exercise the independent Plan guard even if inconsistent legacy data
		# contains an Active Objective under a Draft Plan.
		frappe.db.set_value("OKR Objective", draft_objective.name, "status", "Active")
		invalid_plan_parent = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "Invalid Draft Plan KR",
				"objective": draft_objective.name,
				"assignee": self.users["kr"],
				"metric_type": "Percentage",
				"metric_direction": "Increase",
				"target_value": 100,
				"end_date": draft_objective.end_date,
				"status": "Active",
			}
		)
		with self.assertRaises(frappe.ValidationError):
			invalid_plan_parent.insert(ignore_permissions=True)

	def test_permission_handles_empty_doc_and_string_doc_safely(self):
		# 1. Doctype level create permission check (doc=None)
		frappe.set_user(self.users["action"])
		self.assertTrue(frappe.has_permission("OKR Check In", "create"))
		self.assertTrue(frappe.has_permission("OKR Action Item", "create"))
		self.assertTrue(frappe.has_permission("OKR Key Result", "create"))
		self.assertTrue(frappe.has_permission("OKR Objective", "create"))

		# 2. Blank unsaved new document
		new_chk = frappe.new_doc("OKR Check In")
		self.assertTrue(checkin_permission(new_chk, self.users["action"], "create"))
		self.assertTrue(checkin_permission(new_chk, self.users["action"], "write"))

		# 3. String doc names
		self.assertTrue(frappe.has_permission("OKR Action Item", "read", doc=self.action.name))
		self.assertTrue(frappe.has_permission("OKR Key Result", "read", doc=self.kr.name))
		self.assertTrue(frappe.has_permission("OKR Objective", "read", doc=self.objective.name))

		# 4. OKR Admin can read Plan, OKR User cannot
		frappe.set_user(self.users["okr_admin"])
		self.assertTrue(frappe.has_permission("OKR Plan", "read", doc=self.plan))
		frappe.set_user(self.users["okr_user"])
		self.assertFalse(frappe.has_permission("OKR Plan", "read", doc=self.plan))

	def test_group_read_select_for_okr_user_and_management_administrator_only(self):
		from frappe.desk.form.load import getdoc

		group_name = frappe.db.get_value("Group", {"disabled": 0}, "name")
		if not group_name:
			# Ensure at least one group exists
			g = frappe.get_doc({
				"doctype": "Group",
				"group_name": "Test Admin Perm Group",
				"company": self.company,
			}).insert(ignore_permissions=True)
			group_name = g.name

		# 1. Administrator checks
		frappe.set_user("Administrator")
		self.assertTrue(frappe.has_permission("Group", "read", user="Administrator"))
		self.assertTrue(frappe.has_permission("Group", "write", user="Administrator"))
		self.assertTrue(frappe.has_permission("Group", "create", user="Administrator"))
		self.assertTrue(frappe.has_permission("Group", "delete", user="Administrator"))
		admin_list = frappe.get_list("Group")
		self.assertTrue(len(admin_list) > 0)
		frappe.response["docs"] = []
		getdoc("Group", group_name)
		self.assertTrue(bool(frappe.response.get("docs")))

		# 2. OKR User can read/select existing Groups, but cannot manage them.
		okr_user = self.users["okr_user"]
		frappe.set_user(okr_user)
		self.assertTrue(frappe.has_permission("Group", "read", user=okr_user))
		self.assertTrue(frappe.has_permission("Group", "select", user=okr_user))
		self.assertFalse(frappe.has_permission("Group", "write", user=okr_user))
		self.assertFalse(frappe.has_permission("Group", "create", user=okr_user))
		self.assertFalse(frappe.has_permission("Group", "delete", user=okr_user))
		self.assertEqual(frappe.get_list("Group"), [])
		with self.assertRaises(frappe.PermissionError):
			frappe.new_doc("Group", group_name="Denied Group OKR User", company=self.company).insert()

		# 3. Other non-Administrator roles cannot read or manage Groups.
		test_users = [
			self.users["system"],
			self.users["okr_admin"],
			self.users["outsider"],
		]
		for u in test_users:
			frappe.set_user(u)
			self.assertFalse(frappe.has_permission("Group", "read", user=u))
			self.assertFalse(frappe.has_permission("Group", "write", user=u))
			self.assertFalse(frappe.has_permission("Group", "create", user=u))
			self.assertFalse(frappe.has_permission("Group", "delete", user=u))

			with self.assertRaises(frappe.PermissionError):
				frappe.get_list("Group")

			with self.assertRaises(frappe.PermissionError):
				getdoc("Group", group_name)

			doc = frappe.get_doc("Group", group_name)
			with self.assertRaises(frappe.PermissionError):
				doc.check_permission("read")
			with self.assertRaises(frappe.PermissionError):
				doc.check_permission("write")
			with self.assertRaises(frappe.PermissionError):
				frappe.new_doc("Group", group_name=f"Denied Group {u}", company=self.company).insert()

		# 4. Internal OKR logic (raw DB lookups) remains functional for non-admins
		frappe.set_user(self.users["okr_user"])
		group_val = frappe.db.get_value("Group", group_name, ["name", "company"], as_dict=True)
		self.assertIsNotNone(group_val)
		self.assertEqual(group_val["name"], group_name)

	def test_kr_group_context_and_save_by_normal_okr_user_with_read_select_permission(self):
		from frappe.client import validate_link

		# 1. Setup an objective with Group belonging to self.company
		group_name = frappe.db.get_value("Group", {"company": self.company}, "name")
		if not group_name:
			group = frappe.get_doc({
				"doctype": "Group",
				"group_name": f"Test Group {frappe.generate_hash(length=6)}",
				"company": self.company,
			}).insert(ignore_permissions=True)
			group_name = group.name

		frappe.set_user("Administrator")
		self.objective.group = group_name
		self.objective.save(ignore_permissions=True)

		# 2. Normal permitted OKR user can read/select an existing Group.
		user = self.users["objective"]
		frappe.set_user(user)
		self.assertTrue(frappe.has_permission("Group", "read", user=user))
		self.assertTrue(frappe.has_permission("Group", "select", user=user))

		# Direct Link validation succeeds for an existing Group.
		validate_link("Group", group_name)

		# 3. Normal OKR user creates and saves a Key Result linked to the Objective
		kr = frappe.get_doc({
			"doctype": "OKR Key Result",
			"key_result_title": "Normal User KR With Group " + frappe.generate_hash(length=6),
			"objective": self.objective.name,
			"assignee": self.users["kr"],
			"metric_type": "Percentage",
			"metric_direction": "Increase",
			"target_value": 100,
			"end_date": self.objective.end_date,
			"status": "Draft",
		})
		kr.insert()

		# 4. Verify inherited Group value is saved and persists correctly
		kr.reload()
		self.assertEqual(kr.group, group_name)
		self.assertEqual(kr.parent_plan, self.plan.name)

		# 5. Normal OKR user can edit and save the KR without permission errors
		kr.target_value = 150
		kr.save()
		kr.reload()
		self.assertEqual(kr.target_value, 150)
		self.assertEqual(kr.group, group_name)
