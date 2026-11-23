from __future__ import annotations

import frappe
from frappe.desk.query_report import get_report_doc, run
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate, today

from okr_management.analytics import get_executive_insights
from okr_management.okr_management.report.at_risk_okr_report.at_risk_okr_report import (
	execute as run_at_risk,
)
from okr_management.okr_management.report.employee_okr_progress_report.employee_okr_progress_report import (
	execute as run_employee_progress,
)


class TestSchemaCorrectness(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.reload_reports()
		self.company = frappe.db.get_value("Company", {}, "name")
		self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
		self.fiscal_year = frappe.db.get_value(
			"Fiscal Year",
			{"year_start_date": ["<=", today()], "year_end_date": [">=", today()]},
			"name",
		)
		if not all((self.company, self.department, self.fiscal_year)):
			self.skipTest("Company, Department and Fiscal Year required.")

		self.user = self.make_user("schema-test", ["OKR Admin", "System Manager"])
		self.group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "Schema Correctness " + frappe.generate_hash(length=8),
				"company": self.company,
			}
		).insert(ignore_permissions=True).name

		# Create test plan, objective, key result, action item, check-in
		self.plan = frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "Test Schema Plan " + frappe.generate_hash(length=8),
				"company": self.company,
				"financial_year": self.fiscal_year,
				"status": "Active",
				"owner_user": "Administrator",
			}
		).insert(ignore_permissions=True)

		self.objective_low = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "Low Progress Objective " + frappe.generate_hash(length=8),
				"parent_plan": self.plan.name,
				"company": self.company,
				"department": self.department,
				"group": self.group,
				"owner_user": "Administrator",
				"progress": 35.0,
				"confidence": "2",
				"status": "Active",
			}
		).insert(ignore_permissions=True)

		self.objective_high = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "High Progress Objective " + frappe.generate_hash(length=8),
				"parent_plan": self.plan.name,
				"company": self.company,
				"department": self.department,
				"group": self.group,
				"owner_user": "Administrator",
				"progress": 85.0,
				"confidence": "4",
				"status": "Active",
			}
		).insert(ignore_permissions=True)

		self.kr = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "Test KR " + frappe.generate_hash(length=8),
				"objective": self.objective_low.name,
				"parent_plan": self.plan.name,
				"assignee": "Administrator",
				"target_progress": 40.0,
				"status": "Active",
			}
		).insert(ignore_permissions=True)

		self.kr_high = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "Test KR High " + frappe.generate_hash(length=8),
				"objective": self.objective_high.name,
				"parent_plan": self.plan.name,
				"assignee": "Administrator",
				"target_progress": 85.0,
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("OKR Objective", self.objective_high.name, "progress", 85.0, update_modified=False)
		frappe.db.set_value("OKR Objective", self.objective_low.name, "progress", 35.0, update_modified=False)

		self.action_item = frappe.get_doc(
			{
				"doctype": "OKR Action Item",
				"action_item_title": "Test Action Item " + frappe.generate_hash(length=8),
				"parent_objective": self.objective_low.name,
				"parent_key_result": self.kr.name,
				"parent_plan": self.plan.name,
				"assigned_to": "Administrator",
				"due_date": nowdate(),
				"status": "In Progress",
			}
		).insert(ignore_permissions=True)

		self.checkin = frappe.get_doc(
			{
				"doctype": "OKR Check In",
				"action_item": self.action_item.name,
				"objective": self.objective_low.name,
				"key_result": self.kr.name,
				"parent_plan": self.plan.name,
				"reported_by": "Administrator",
				"checkin_date": nowdate(),
				"progress_percent": 30.0,
				"self_rating": 0.8,
				"confidence": "Green",
				"status": "Submitted",
				"review_status": "Approved",
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def reload_reports(self):
		modules = {
			"Low Performance Objectives": "low_performance_objectives",
			"Pending Reviews": "pending_reviews",
			"OKR Check-in Aging": "okr_checkin_aging",
			"Department Performance": "department_performance",
			"Employee Performance": "employee_performance",
			"OKR Objective Progress": "okr_objective_progress",
		}
		for name, mod in modules.items():
			frappe.reload_doc("okr_management", "report", mod)

	def make_user(self, suffix, roles):
		email = f"okr.schema-test.{suffix}@example.com"
		if not frappe.db.exists("User", email):
			previous_in_import = frappe.flags.in_import
			frappe.flags.in_import = True
			try:
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": "Schema Test",
						"send_welcome_email": 0,
						"user_type": "System User",
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

	def test_low_performance_objectives_report(self):
		res = run("Low Performance Objectives", filters={})
		columns = [c["fieldname"] if isinstance(c, dict) else c for c in res.get("columns", [])]
		self.assertIn("parent_plan", columns)
		self.assertNotIn("plan", columns)
		rows = res.get("result", [])
		titles = [r.get("objective_title") if isinstance(r, dict) else r[1] for r in rows]
		self.assertIn(self.objective_low.objective_title, titles)
		self.assertNotIn(self.objective_high.objective_title, titles)

	def test_pending_reviews_report(self):
		frappe.db.set_value(
			"OKR Check In", self.checkin.name, "review_status", "Submitted", update_modified=False
		)
		res = run("Pending Reviews", filters={})
		columns = [c["fieldname"] if isinstance(c, dict) else c for c in res.get("columns", [])]
		self.assertNotIn("manager_rating", columns)
		rows = res.get("result", [])
		names = [r.get("name") if isinstance(r, dict) else r[0] for r in rows]
		self.assertIn(self.checkin.name, names)

		frappe.db.set_value(
			"OKR Check In", self.checkin.name, "review_status", "Approved", update_modified=False
		)
		res = run("Pending Reviews", filters={})
		rows = res.get("result", [])
		names = [r.get("name") if isinstance(r, dict) else r[0] for r in rows]
		self.assertNotIn(self.checkin.name, names)

	def test_okr_checkin_aging_report(self):
		res = run("OKR Check-in Aging", filters={})
		columns = [c["fieldname"] if isinstance(c, dict) else c for c in res.get("columns", [])]
		self.assertNotIn("manager_rating", columns)
		rows = res.get("result", [])
		names = [r.get("name") if isinstance(r, dict) else r[0] for r in rows]
		self.assertIn(self.checkin.name, names)

	def test_reports_with_plan_filter(self):
		# Test script reports with plan filter to confirm parent_plan resolution
		at_risk_cols, at_risk_data = run_at_risk({"plan": self.plan.name})
		self.assertTrue(any(row.get("record") == self.objective_low.name for row in at_risk_data))

		emp_cols, emp_data = run_employee_progress({"plan": self.plan.name})
		self.assertTrue(len(emp_data) >= 1)

	def test_unmocked_executive_insights(self):
		# Must run directly against real database without any mocking of frappe.get_all
		frappe.set_user("Administrator")
		res = get_executive_insights()
		self.assertIn("at_risk_objectives", res)
		self.assertIn("key_results_need_attention", res)
		self.assertIn("owners_without_recent_update", res)
		self.assertIn("recommended_next_actions", res)

		# Test authorized OKR Admin
		frappe.set_user(self.user)
		res_admin = get_executive_insights()
		self.assertEqual(len(res["at_risk_objectives"]), len(res_admin["at_risk_objectives"]))
