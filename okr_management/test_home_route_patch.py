from __future__ import annotations

from pathlib import Path

import frappe
from frappe.boot import load_desktop_data
from frappe.desk.desk_page import get as get_desk_page
from frappe.desk.desktop import get_workspace_sidebar_items as get_core_workspace_sidebar_items
from frappe.tests.utils import FrappeTestCase
from frappe.utils import slug

from okr_management.okr_management.page.admin_workspace.admin_workspace import get_dashboard_data
from okr_management.okr_management.page.okr_workspace.okr_workspace import get_workspace_data
from okr_management.navigation import (
	ADMIN_WORKSPACES,
	USER_WORKSPACES,
	get_workspace_sidebar_items,
)
from okr_management.patches.v0_0_51_restrict_okr_home_workspaces import (
	ADMIN_WORKSPACE,
	LEGACY_ADMIN_WORKSPACE,
	USER_WORKSPACE,
	execute,
)
from okr_management.patches.v0_0_52_restrict_okr_plan_route import (
	PLAN_WORKSPACE,
	execute as restrict_plan_route,
)


class TestOKRHomeRoutePatch(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.reload_doc("okr_management", "workspace", "admin_workspace")
		frappe.reload_doc("okr_management", "workspace", "okr_workspace")
		self.admin = self.make_user("admin", ["OKR Admin"])
		self.system_manager = self.make_user("system-manager", ["System Manager"])
		self.okr_user = self.make_user("okr-user", ["OKR User"])
		self.desk_user = self.make_user("desk-user", [])
		self.website_user = self.make_user("website-user", [], user_type="Website User")
		self.website_okr_user = self.make_user(
			"website-okr-user", ["OKR User"], user_type="Website User"
		)
		self.disabled_user = self.make_user("disabled-user", ["OKR User"], enabled=0)

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_user(
		self,
		suffix: str,
		roles: list[str],
		*,
		user_type: str = "System User",
		enabled: int = 1,
	) -> str:
		email = f"okr.home-route.{suffix}.{frappe.generate_hash(length=8)}@example.com"
		previous_in_import = frappe.flags.in_import
		frappe.flags.in_import = True
		try:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "OKR Home Route",
					"send_welcome_email": 0,
					"user_type": user_type,
					"enabled": enabled,
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.flags.in_import = previous_in_import
		if roles:
			user.add_roles(*roles)
			frappe.clear_cache(user=email)
		# add_roles() promotes Website Users that receive Desk roles to System Users.
		# Restore the requested state so the migration guard covers inconsistent legacy data.
		if user_type != "System User":
			frappe.db.set_value("User", email, "user_type", user_type, update_modified=False)
		if not enabled:
			frappe.db.set_value("User", email, "enabled", 0, update_modified=False)
		if user_type != "System User" or not enabled:
			frappe.clear_document_cache("User", email)
		return email

	def set_default(self, user: str, workspace: str | None) -> None:
		frappe.db.set_value("User", user, "default_workspace", workspace, update_modified=False)
		frappe.clear_document_cache("User", user)

	def workspace_roles(self, workspace: str) -> list[str]:
		return self.assigned_roles("Workspace", workspace)

	def assigned_roles(self, parenttype: str, parent: str) -> list[str]:
		return frappe.get_all(
			"Has Role",
			filters={
				"parent": parent,
				"parenttype": parenttype,
				"parentfield": "roles",
			},
			order_by="idx asc",
			pluck="role",
		)

	def allowed_okr_workspaces(self, user: str) -> set[str]:
		frappe.set_user(user)
		return {
			page.name
			for page in get_core_workspace_sidebar_items()["pages"]
			if page.module == "OKR Management"
		}

	def boot_workspaces(self, user: str) -> list[frappe._dict]:
		frappe.set_user(user)
		bootinfo = frappe._dict()
		load_desktop_data(bootinfo)
		return bootinfo.allowed_workspaces

	def resolve_app_route(self, user: str) -> str | None:
		pages = self.boot_workspaces(user)
		workspace_by_slug = {slug(page.name): page for page in pages}
		default_workspace = frappe.db.get_value("User", user, "default_workspace")
		workspace = workspace_by_slug.get(slug(default_workspace or ""))
		if not workspace and pages:
			workspace = pages[0]
		if not workspace:
			return None
		return "/app/" + ("" if workspace.public else "private/") + slug(workspace.title)

	def assert_page_access(self, user: str, page: str, allowed: bool) -> None:
		frappe.set_user(user)
		frappe.local.response = frappe._dict()
		if allowed:
			self.assertEqual(get_desk_page(page).name, page)
		else:
			with self.assertRaises(frappe.PermissionError):
				get_desk_page(page)

	def okr_data_snapshot(self) -> dict[str, list[dict]]:
		fields = {
			"OKR Plan": ["name", "status", "owner_user"],
			"OKR Objective": ["name", "parent_plan", "status", "owner_user", "progress"],
			"OKR Key Result": ["name", "objective", "status", "assignee", "current_value", "target_progress"],
			"OKR Action Item": ["name", "parent_key_result", "status", "assigned_to", "current_value", "progress"],
			"OKR Check In": ["name", "action_item", "key_result", "objective", "status", "current_value"],
			"OKR Objective Review": ["name", "objective", "reviewer", "review_status", "manager_rating"],
		}
		return {
			doctype: frappe.get_all(doctype, fields=doctype_fields, order_by="name asc")
			for doctype, doctype_fields in fields.items()
		}

	def test_workspace_roles_are_synchronized_idempotently(self):
		execute()
		execute()
		restrict_plan_route()
		restrict_plan_route()

		self.assertEqual(self.workspace_roles(ADMIN_WORKSPACE), ["OKR Admin", "System Manager"])
		self.assertEqual(self.workspace_roles(USER_WORKSPACE), ["OKR User", "System Manager"])
		self.assertEqual(self.workspace_roles(PLAN_WORKSPACE), ["OKR Admin", "System Manager"])
		self.assertEqual(self.assigned_roles("Page", "okr-workspace"), ["OKR User", "System Manager"])

	def test_core_boot_workspace_visibility_matches_roles(self):
		execute()
		restrict_plan_route()

		self.assertIn(ADMIN_WORKSPACE, self.allowed_okr_workspaces(self.admin))
		self.assertNotIn(USER_WORKSPACE, self.allowed_okr_workspaces(self.admin))
		self.assertNotIn(ADMIN_WORKSPACE, self.allowed_okr_workspaces(self.okr_user))
		self.assertIn(USER_WORKSPACE, self.allowed_okr_workspaces(self.okr_user))
		self.assertNotIn(ADMIN_WORKSPACE, self.allowed_okr_workspaces(self.desk_user))
		self.assertNotIn(USER_WORKSPACE, self.allowed_okr_workspaces(self.desk_user))
		self.assertIn(ADMIN_WORKSPACE, self.allowed_okr_workspaces(self.system_manager))
		self.assertIn(USER_WORKSPACE, self.allowed_okr_workspaces(self.system_manager))
		self.assertIn(PLAN_WORKSPACE, self.allowed_okr_workspaces(self.admin))
		self.assertIn(PLAN_WORKSPACE, self.allowed_okr_workspaces(self.system_manager))
		self.assertNotIn(PLAN_WORKSPACE, self.allowed_okr_workspaces(self.okr_user))
		self.assertNotIn(PLAN_WORKSPACE, self.allowed_okr_workspaces(self.desk_user))

	def test_plan_workspace_default_is_removed_only_for_unauthorized_users(self):
		self.set_default(self.admin, PLAN_WORKSPACE)
		self.set_default(self.system_manager, PLAN_WORKSPACE)
		self.set_default(self.okr_user, PLAN_WORKSPACE)
		self.set_default(self.desk_user, PLAN_WORKSPACE)

		restrict_plan_route()

		self.assertEqual(frappe.db.get_value("User", self.admin, "default_workspace"), PLAN_WORKSPACE)
		self.assertEqual(
			frappe.db.get_value("User", self.system_manager, "default_workspace"), PLAN_WORKSPACE
		)
		self.assertIsNone(frappe.db.get_value("User", self.okr_user, "default_workspace"))
		self.assertIsNone(frappe.db.get_value("User", self.desk_user, "default_workspace"))

	def test_invalid_admin_default_is_corrected_by_role(self):
		self.assertIn("OKR Admin", frappe.get_roles(self.admin))
		self.assertIn("System Manager", frappe.get_roles(self.system_manager))
		self.assertIn("OKR User", frappe.get_roles(self.okr_user))
		self.assertEqual(frappe.db.get_value("User", self.admin, "user_type"), "System User")
		self.assertEqual(frappe.db.get_value("User", self.admin, "enabled"), 1)
		for user in (
			"Administrator",
			self.admin,
			self.system_manager,
			self.okr_user,
			self.desk_user,
			self.website_okr_user,
			self.disabled_user,
		):
			self.set_default(user, LEGACY_ADMIN_WORKSPACE)

		execute()

		self.assertEqual(
			frappe.db.get_value("User", "Administrator", "default_workspace"),
			ADMIN_WORKSPACE,
		)
		self.assertEqual(frappe.db.get_value("User", self.admin, "default_workspace"), ADMIN_WORKSPACE)
		self.assertEqual(
			frappe.db.get_value("User", self.system_manager, "default_workspace"),
			ADMIN_WORKSPACE,
		)
		self.assertEqual(frappe.db.get_value("User", self.okr_user, "default_workspace"), USER_WORKSPACE)
		self.assertIsNone(frappe.db.get_value("User", self.desk_user, "default_workspace"))
		self.assertIsNone(frappe.db.get_value("User", self.website_okr_user, "default_workspace"))
		self.assertIsNone(frappe.db.get_value("User", self.disabled_user, "default_workspace"))

	def test_actual_admin_workspace_is_corrected_only_when_access_is_invalid(self):
		self.set_default(self.admin, ADMIN_WORKSPACE)
		self.set_default(self.okr_user, ADMIN_WORKSPACE)
		self.set_default(self.desk_user, ADMIN_WORKSPACE)

		execute()

		self.assertEqual(frappe.db.get_value("User", self.admin, "default_workspace"), ADMIN_WORKSPACE)
		self.assertEqual(frappe.db.get_value("User", self.okr_user, "default_workspace"), USER_WORKSPACE)
		self.assertIsNone(frappe.db.get_value("User", self.desk_user, "default_workspace"))

	def test_non_admin_default_is_not_changed(self):
		self.set_default(self.desk_user, USER_WORKSPACE)

		execute()

		self.assertEqual(
			frappe.db.get_value("User", self.desk_user, "default_workspace"),
			USER_WORKSPACE,
		)

	def test_repeated_execution_preserves_corrected_defaults(self):
		self.set_default(self.okr_user, LEGACY_ADMIN_WORKSPACE)
		self.set_default(self.website_okr_user, LEGACY_ADMIN_WORKSPACE)

		execute()
		execute()

		self.assertEqual(frappe.db.get_value("User", self.okr_user, "default_workspace"), USER_WORKSPACE)
		self.assertIsNone(frappe.db.get_value("User", self.website_okr_user, "default_workspace"))

	def test_seven_profile_boot_and_app_route_matrix(self):
		for user in ("Administrator", self.admin, self.system_manager, self.okr_user, self.desk_user):
			self.set_default(user, LEGACY_ADMIN_WORKSPACE)
		self.set_default(self.website_user, LEGACY_ADMIN_WORKSPACE)
		self.set_default(self.disabled_user, LEGACY_ADMIN_WORKSPACE)

		execute()

		expected_okr_workspaces = {
			"Administrator": {ADMIN_WORKSPACE, USER_WORKSPACE},
			self.admin: {ADMIN_WORKSPACE},
			self.system_manager: {ADMIN_WORKSPACE, USER_WORKSPACE},
			self.okr_user: {USER_WORKSPACE},
			self.desk_user: set(),
			self.website_user: set(),
		}
		for user, expected in expected_okr_workspaces.items():
			actual_roots = {
				page.name for page in self.boot_workspaces(user) if page.module == "OKR Management"
			} & {ADMIN_WORKSPACE, USER_WORKSPACE}
			self.assertEqual(actual_roots, expected, user)

		expected_visible = {
			"Administrator": ADMIN_WORKSPACES | USER_WORKSPACES,
			self.admin: ADMIN_WORKSPACES,
			self.system_manager: ADMIN_WORKSPACES | USER_WORKSPACES,
			self.okr_user: USER_WORKSPACES,
			self.desk_user: set(),
			self.website_user: set(),
		}
		existing_okr_workspaces = set(
			frappe.get_all("Workspace", filters={"module": "OKR Management"}, pluck="name")
		)
		for user, expected in expected_visible.items():
			frappe.set_user(user)
			visible = {
				page.name
				for page in get_workspace_sidebar_items()["pages"]
				if page.module == "OKR Management"
			}
			self.assertEqual(visible, expected & existing_okr_workspaces, user)

		self.assertEqual(self.resolve_app_route("Administrator"), "/app/okr-admin-workspace")
		self.assertEqual(self.resolve_app_route(self.admin), "/app/okr-admin-workspace")
		self.assertEqual(self.resolve_app_route(self.system_manager), "/app/okr-admin-workspace")
		self.assertEqual(self.resolve_app_route(self.okr_user), "/app/okr-workspace")
		desk_route = self.resolve_app_route(self.desk_user)
		self.assertIsNotNone(desk_route)
		self.assertNotIn(desk_route, {"/app/okr-admin-workspace", "/app/okr-workspace"})
		self.assertIsNone(frappe.db.get_value("User", self.website_user, "default_workspace"))
		self.assertIsNone(frappe.db.get_value("User", self.disabled_user, "default_workspace"))

	def test_navbar_home_route_and_admin_alias_do_not_loop(self):
		navbar = Path(
			frappe.get_app_path("frappe", "public", "js", "frappe", "ui", "toolbar", "navbar.html")
		).read_text(encoding="utf-8")
		alias = Path(
			frappe.get_app_path(
				"okr_management",
				"okr_management",
				"page",
				"okr_admin_workspace",
				"okr_admin_workspace.js",
			)
		).read_text(encoding="utf-8")

		self.assertIn('class="navbar-brand navbar-home" href="/app"', navbar)
		self.assertIn('frappe.set_route("admin-workspace")', alias)
		self.assertNotIn('frappe.set_route("okr-admin-workspace")', alias)

		global_source = Path(
			frappe.get_app_path("okr_management", "public", "js", "okr_management.js")
		).read_text(encoding="utf-8")
		self.assertIn('"OKR Plan"', global_source)
		self.assertIn('path === "/app/okr-plan"', global_source)
		self.assertIn('frappe.set_route("home")', global_source)
		self.assertIn('frappe.user?.has_role?.(role)', global_source)

	def test_page_and_backend_access_matrix(self):
		execute()
		matrix = {
			"Administrator": (True, True),
			self.admin: (True, False),
			self.system_manager: (True, True),
			self.okr_user: (False, True),
			self.desk_user: (False, False),
			self.website_user: (False, False),
		}
		for user, (admin_allowed, user_allowed) in matrix.items():
			with self.subTest(user=user, page="okr-admin-workspace"):
				self.assert_page_access(user, "okr-admin-workspace", admin_allowed)
			with self.subTest(user=user, page="admin-workspace"):
				self.assert_page_access(user, "admin-workspace", admin_allowed)
			with self.subTest(user=user, page="okr-workspace"):
				self.assert_page_access(user, "okr-workspace", user_allowed)

			frappe.set_user(user)
			if admin_allowed:
				self.assertIsInstance(get_dashboard_data(), dict)
			else:
				with self.assertRaises(frappe.PermissionError):
					get_dashboard_data()
			# The user Workspace API is hierarchy-limited and returns an empty payload
			# rather than raising when a user has no visible OKR records.
			self.assertIsInstance(get_workspace_data(), dict)

	def test_disabled_user_cannot_receive_a_desk_home(self):
		self.set_default(self.disabled_user, LEGACY_ADMIN_WORKSPACE)

		execute()

		self.assertEqual(frappe.db.get_value("User", self.disabled_user, "enabled"), 0)
		self.assertIsNone(frappe.db.get_value("User", self.disabled_user, "default_workspace"))

	def test_patch_does_not_change_existing_okr_data(self):
		before = self.okr_data_snapshot()

		execute()
		execute()

		self.assertEqual(self.okr_data_snapshot(), before)
