from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today


class TestOKRActionItem(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
		self.employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
		self.fiscal_year = frappe.db.get_value(
			"Fiscal Year", {"year_start_date": ["<=", today()], "year_end_date": [">=", today()]}, "name"
		)
		if not all((self.company, self.department, self.employee, self.fiscal_year)):
			self.skipTest("Required ERP masters are missing.")
		fy = frappe.db.get_value(
			"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
		)
		self.plan = frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "AI Test " + frappe.generate_hash(length=6),
				"financial_year": self.fiscal_year,
				"company": self.company,
				"owner_user": "Administrator",
				"sprint_frequency": "Monthly",
				"planned_activation_date": fy.year_start_date,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		self.plan.status = "Active"
		self.plan.save(ignore_permissions=True)
		self.objective = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "AI Objective " + frappe.generate_hash(length=6),
				"parent_plan": self.plan.name,
				"level": "Department",
				"level_details": self.department,
				"department": self.department,
				"owner_user": "Administrator",
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		self.kr = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "AI KR " + frappe.generate_hash(length=6),
				"objective": self.objective.name,
				"assignee": "Administrator",
				"metric_type": "Percentage",
				"metric_direction": "Increase",
				"target_value": 100,
				"end_date": self.objective.end_date,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)

	def make_action(self, **values):
		payload = {
			"doctype": "OKR Action Item",
			"action_item_title": "AI Test " + frappe.generate_hash(length=6),
			"parent_key_result": self.kr.name,
			"assigned_to": "Administrator",
			"due_date": self.kr.end_date,
		}
		payload.update(values)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def test_due_date_is_required_without_today_default(self):
		self.assertRaises(frappe.ValidationError, self.make_action, due_date=None)

	def test_due_date_must_stay_inside_key_result(self):
		self.assertRaises(frappe.ValidationError, self.make_action, due_date=add_days(self.kr.end_date, 1))

	def test_due_date_is_editable_inside_target_period(self):
		due = add_days(self.kr.end_date, -2)
		self.assertEqual(getdate(self.make_action(due_date=due).due_date), getdate(due))

	def test_due_date_can_use_full_objective_timeline(self):
		due = add_days(self.kr.start_date, 10)
		self.assertEqual(getdate(self.make_action(due_date=due).due_date), getdate(due))

	def test_context_and_assignment_are_inherited(self):
		action = self.make_action()
		self.assertEqual(action.parent_objective, self.objective.name)
		self.assertEqual(action.parent_plan, self.plan.name)

	def test_completion_date_updates(self):
		action = self.make_action()
		action.status = "Completed"
		action.save(ignore_permissions=True)
		self.assertIsNotNone(action.completion_date)
