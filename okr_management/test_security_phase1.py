from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.desk.query_report import get_report_doc, run
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from okr_management.analytics import (
	average_objective_confidence,
	average_objective_progress,
	average_review_rating,
	checkins_this_month_count,
	get_executive_insights,
	pending_reviews_count,
)
from okr_management.hierarchy_visibility import get_hierarchy_visibility_scope
from okr_management.okr_management.dashboard_chart_source.okr_confidence_distribution import (
	okr_confidence_distribution,
)
from okr_management.okr_management.dashboard_chart_source.okr_key_results_by_progress_range import (
	okr_key_results_by_progress_range,
)
from okr_management.okr_management.dashboard_chart_source.okr_review_rating_distribution import (
	okr_review_rating_distribution,
)
from okr_management.okr_management.doctype.okr_objective.okr_objective import (
	get_team_options,
	search_available_plans,
)
from okr_management.okr_management.doctype.okr_objective_review.okr_objective_review import (
	get_derived_self_rating,
)
from okr_management.okr_management.doctype.okr_plan.okr_plan import get_plan_context


ADMIN_REPORTS = (
	"Department Performance",
	"Employee Performance",
	"Low Performance Objectives",
	"OKR Check-in Aging",
	"OKR Objective Progress",
	"Pending Reviews",
)

REPORT_MODULE_NAMES = {
	"OKR Check-in Aging": "okr_checkin_aging",
}


class TestSecurityPhase1(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.reload_doc("okr_management", "doctype", "okr_objective")
		frappe.reload_doc("okr_management", "doctype", "okr_check_in")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
		self.fiscal_year = frappe.db.get_value(
			"Fiscal Year",
			{"year_start_date": ["<=", today()], "year_end_date": [">=", today()]},
			"name",
		)
		if not all((self.company, self.department, self.fiscal_year)):
			self.skipTest("Company, Department and current Fiscal Year are required.")

		self.users = {
			"okr_admin": self.make_user("okr-admin", ["OKR Admin"]),
			"dual_admin": self.make_user("dual-admin", ["OKR Admin", "OKR User"]),
			"system_manager": self.make_user("system-manager", ["System Manager"]),
			"okr_user": self.make_user("okr-user", ["OKR User"]),
			"normal": self.make_user("normal", []),
			"website": self.make_user("website", [], user_type="Website User"),
		}
		self.group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "Security Phase 1 " + frappe.generate_hash(length=8),
				"company": self.company,
			}
		).insert(ignore_permissions=True).name
		self.member_plan = self.make_plan(self.users["okr_user"])
		self.empty_member_plan = self.make_plan(self.users["okr_user"])
		self.visible_plan = self.make_plan("Administrator")
		self.other_plan = self.make_plan("Administrator")
		self.member_objective = self.make_objective(self.member_plan, self.users["okr_user"])
		self.visible_objective = self.make_objective(self.visible_plan, self.users["okr_user"])
		self.other_objective = self.make_objective(self.other_plan, "Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_user(self, suffix, roles, *, user_type="System User"):
		email = f"okr.security-phase1.{suffix}@example.com"
		if not frappe.db.exists("User", email):
			previous_in_import = frappe.flags.in_import
			frappe.flags.in_import = True
			try:
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": "Security Phase 1",
						"send_welcome_email": 0,
						"user_type": user_type,
						"enabled": 1,
					}
				).insert(ignore_permissions=True)
			finally:
				frappe.flags.in_import = previous_in_import
		user = frappe.get_doc("User", email)
		if roles:
			user.add_roles(*roles)
		frappe.clear_cache(user=email)
		return email

	def make_plan(self, member):
		return frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "Security Plan " + frappe.generate_hash(length=8),
				"financial_year": self.fiscal_year,
				"company": self.company,
				"owner_user": member,
				"status": "Active",
				"members": [{"member_user": member, "role": "Plan Coordinator"}],
			}
		).insert(ignore_permissions=True)

	def make_objective(self, plan, owner):
		return frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "Security Objective " + frappe.generate_hash(length=8),
				"parent_plan": plan.name,
				"department": self.department,
				"group": self.group,
				"owner_user": owner,
				"status": "Active",
			}
		).insert(ignore_permissions=True)

	def test_h2_executive_insights_role_matrix(self):
		authorized = ("Administrator", self.users["okr_admin"], self.users["system_manager"])
		baseline = None
		with patch("okr_management.analytics.frappe.get_all", return_value=[]):
			for user in authorized:
				frappe.set_user(user)
				result = get_executive_insights()
				baseline = result if baseline is None else baseline
				self.assertEqual(result, baseline)

		for user in (self.users["okr_user"], self.users["normal"], self.users["website"]):
			frappe.set_user(user)
			with patch("okr_management.analytics.frappe.get_all") as get_all:
				with self.assertRaises(frappe.PermissionError):
					get_executive_insights()
				payload_doctypes = {"OKR Objective", "OKR Key Result", "OKR Check In"}
				self.assertFalse(
					any(call.args and call.args[0] in payload_doctypes for call in get_all.call_args_list)
				)

	def test_h3_query_report_role_matrix(self):
		for report_name in ADMIN_REPORTS:
			frappe.reload_doc(
				"okr_management",
				"report",
				REPORT_MODULE_NAMES.get(report_name, frappe.scrub(report_name)),
			)

		for user in (self.users["okr_user"], self.users["normal"], self.users["website"]):
			frappe.set_user(user)
			with patch(
				"frappe.core.doctype.report.report.Report.execute_query_report"
			) as execute_query_report:
				for report_name in ADMIN_REPORTS:
					with self.assertRaises(frappe.PermissionError):
						get_report_doc(report_name)
					with self.assertRaises(frappe.PermissionError):
						run(report_name, filters={})
				execute_query_report.assert_not_called()

		baselines = {}
		for user in ("Administrator", self.users["okr_admin"], self.users["system_manager"]):
			frappe.set_user(user)
			with patch(
				"frappe.core.doctype.report.report.Report.execute_query_report",
				return_value=[["value"], [[1]]],
			):
				for report_name in ADMIN_REPORTS:
					self.assertEqual(get_report_doc(report_name).name, report_name)
					result = run(report_name, filters={})
					baselines.setdefault(report_name, result)
					self.assertEqual(result, baselines[report_name])

	def test_h5_plan_context_role_and_membership_matrix(self):
		frappe.set_user("Administrator")
		baseline = get_plan_context(self.other_plan.name)
		for user in (self.users["okr_admin"], self.users["system_manager"]):
			frappe.set_user(user)
			self.assertEqual(get_plan_context(self.other_plan.name), baseline)

		frappe.set_user(self.users["okr_user"])
		self.assertFalse(
			frappe.db.exists("OKR Objective", {"parent_plan": self.empty_member_plan.name})
		)
		first_objective_context = get_plan_context(self.empty_member_plan.name)
		self.assertEqual(first_objective_context["parent_plan"], self.empty_member_plan.name)
		member_result = get_plan_context(self.member_plan.name)
		self.assertEqual(member_result["parent_plan"], self.member_plan.name)
		with self.assertRaises(frappe.PermissionError):
			get_plan_context(self.visible_plan.name)
		with self.assertRaises(frappe.PermissionError):
			get_plan_context(self.other_plan.name)
		self.assertNotIn(
			self.users["okr_user"],
			{row.member_user for row in self.other_plan.members},
		)

		for user in (self.users["normal"], self.users["website"]):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_plan_context(self.other_plan.name)

	def test_h6_derived_rating_role_and_object_permission_matrix(self):
		original_sql = frappe.db.sql
		rating_result = [(0.72,)]

		def controlled_rating_query(query, *args, **kwargs):
			if "tabOKR Check In" in str(query):
				return rating_result
			return original_sql(query, *args, **kwargs)

		with patch.object(frappe.db, "sql", side_effect=controlled_rating_query):
			for user in ("Administrator", self.users["okr_admin"], self.users["system_manager"]):
				frappe.set_user(user)
				self.assertEqual(get_derived_self_rating(self.other_objective.name), 0.72)

		frappe.set_user(self.users["okr_user"])
		with patch.object(frappe.db, "sql", side_effect=controlled_rating_query):
			self.assertEqual(get_derived_self_rating(self.member_objective.name), 0.72)
		with patch.object(frappe.db, "sql", side_effect=controlled_rating_query) as sql:
			with self.assertRaises(frappe.PermissionError):
				get_derived_self_rating(self.other_objective.name)
			self.assertFalse(any("tabOKR Check In" in str(call.args[0]) for call in sql.call_args_list))

		for user in (self.users["normal"], self.users["website"]):
			frappe.set_user(user)
			with patch.object(frappe.db, "sql", side_effect=controlled_rating_query) as sql:
				with self.assertRaises(frappe.PermissionError):
					get_derived_self_rating(self.other_objective.name)
				self.assertFalse(
					any("tabOKR Check In" in str(call.args[0]) for call in sql.call_args_list)
				)

	def test_okr_admin_scope_with_and_without_okr_user_role(self):
		for user in (self.users["okr_admin"], self.users["dual_admin"]):
			scope = get_hierarchy_visibility_scope(user)
			self.assertTrue(scope["read_all"])
			self.assertFalse(scope["visible_objectives"])

		for user in (self.users["okr_user"], self.users["normal"], self.users["website"]):
			scope = get_hierarchy_visibility_scope(user)
			self.assertFalse(scope["read_all"])

	def test_m1_analytics_and_dashboard_sources_require_okr_admin(self):
		analytics_functions = (
			average_objective_progress,
			average_objective_confidence,
			pending_reviews_count,
			checkins_this_month_count,
			average_review_rating,
		)
		chart_modules = (
			okr_confidence_distribution,
			okr_key_results_by_progress_range,
			okr_review_rating_distribution,
		)
		for user in (self.users["okr_user"], self.users["normal"], self.users["website"]):
			frappe.set_user(user)
			with patch("okr_management.analytics.frappe.get_all") as get_all:
				for function in analytics_functions:
					with self.assertRaises(frappe.PermissionError):
						function()
				payload_doctypes = {
					"OKR Objective",
					"OKR Objective Review",
					"OKR Key Result",
					"OKR Check In",
				}
				self.assertFalse(
					any(
						call.args and call.args[0] in payload_doctypes
						for call in get_all.call_args_list
					)
				)
			for module in chart_modules:
				with patch.object(module, "_get") as get_data:
					with self.assertRaises(frappe.PermissionError):
						module.get()
					get_data.assert_not_called()

		for user in ("Administrator", self.users["okr_admin"], self.users["system_manager"]):
			frappe.set_user(user)
			with patch("okr_management.analytics._avg", return_value=12.5):
				self.assertEqual(average_objective_progress(), 12.5)
			for module in chart_modules:
				with patch.object(module, "_get", return_value={"labels": [], "datasets": []}):
					self.assertEqual(module.get(), {"labels": [], "datasets": []})

	def test_m2_team_and_plan_search_authorization(self):
		for user in (self.users["normal"], self.users["website"]):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				get_team_options("User", "", "name", 0, 20, {})
			with self.assertRaises(frappe.PermissionError):
				search_available_plans("OKR Plan", "", "name", 0, 100, {})

		frappe.set_user(self.users["okr_user"])
		self.assertTrue(get_team_options("User", "", "name", 0, 20, {}))
		plan_rows = search_available_plans("OKR Plan", "", "name", 0, 100, {})
		plan_names = {row[0] for row in plan_rows}
		self.assertIn(self.member_plan.name, plan_names)
		self.assertIn(self.empty_member_plan.name, plan_names)
		self.assertIn(self.other_plan.name, plan_names)

		frappe.set_user(self.users["okr_admin"])
		admin_names = {
			row[0] for row in search_available_plans("OKR Plan", "", "name", 0, 100, {})
		}
		self.assertIn(self.member_plan.name, admin_names)
		self.assertIn(self.other_plan.name, admin_names)

	def test_m3_action_item_report_applies_hierarchy_scope(self):
		from okr_management.okr_management.report.okr_action_item_report import (
			okr_action_item_report as report,
		)

		empty_scope = {"read_all": False, "visible_action_items": set()}
		with patch.object(report, "get_hierarchy_visibility_scope", return_value=empty_scope):
			with patch.object(report.frappe.db, "sql", return_value=[]) as sql:
				self.assertEqual(report.execute({})[1], [])
				self.assertIn("1=0", sql.call_args.args[0])

		visible_scope = {"read_all": False, "visible_action_items": {"ACTION-2", "ACTION-1"}}
		with patch.object(report, "get_hierarchy_visibility_scope", return_value=visible_scope):
			with patch.object(report.frappe.db, "sql", return_value=[]) as sql:
				report.execute({})
				query, values = sql.call_args.args[:2]
				self.assertIn("ai.name in", query)
				self.assertEqual(set(values.values()), {"ACTION-1", "ACTION-2"})

	def test_m3_summary_report_applies_hierarchy_scope(self):
		from okr_management.okr_management.report.okr_summary_report import okr_summary_report as report

		empty_scope = {
			"read_all": False,
			"visible_objectives": set(),
			"visible_key_results": set(),
		}
		with patch.object(report, "get_hierarchy_visibility_scope", return_value=empty_scope):
			with patch.object(report.frappe.db, "sql", return_value=[]) as sql:
				self.assertEqual(report.execute({})[1], [])
				self.assertIn("1=0", sql.call_args.args[0])

		visible_scope = {
			"read_all": False,
			"visible_objectives": {"OBJECTIVE-1"},
			"visible_key_results": {"KR-1"},
		}
		with patch.object(report, "get_hierarchy_visibility_scope", return_value=visible_scope):
			with patch.object(report.frappe.db, "sql", return_value=[]) as sql:
				report.execute({})
				query, values = sql.call_args.args[:2]
				self.assertIn("kr.name in", query)
				self.assertIn("kr.name is null and obj.name in", query)
				self.assertEqual(set(values.values()), {"OBJECTIVE-1", "KR-1"})
