from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


class TestPlanStartStructuralLock(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
		self.fiscal_year = frappe.db.get_value(
			"Fiscal Year",
			{"year_start_date": ["<=", today()], "year_end_date": [">=", add_days(today(), 1)]},
			"name",
		)
		if not all((self.company, self.department, self.fiscal_year)):
			self.skipTest("Current ERP masters and a Fiscal Year covering tomorrow are required.")
		self.group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "Plan Lock " + frappe.generate_hash(length=8),
				"company": self.company,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_hierarchy(self, activation_date):
		plan = frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "Lock Plan " + frappe.generate_hash(length=8),
				"financial_year": self.fiscal_year,
				"company": self.company,
				"owner_user": "Administrator",
				"sprint_frequency": "Monthly",
				"planned_activation_date": activation_date,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		objective = frappe.get_doc(
			{
				"doctype": "OKR Objective",
				"objective_title": "Lock Objective " + frappe.generate_hash(length=8),
				"parent_plan": plan.name,
				"group": self.group.name,
				"department": self.department,
				"owner_user": "Administrator",
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		key_result = frappe.get_doc(
			{
				"doctype": "OKR Key Result",
				"key_result_title": "Lock KR " + frappe.generate_hash(length=8),
				"objective": objective.name,
				"assignee": "Administrator",
				"metric_type": "Number",
				"metric_direction": "Increase",
				"baseline_value": 0,
				"current_value": 0,
				"target_value": 100,
				"calculation_mode": "Automatic",
				"end_date": objective.end_date,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		action = frappe.get_doc(
			{
				"doctype": "OKR Action Item",
				"action_item_title": "Lock Action " + frappe.generate_hash(length=8),
				"parent_key_result": key_result.name,
				"assigned_to": "Administrator",
				"due_date": key_result.end_date,
			}
		).insert(ignore_permissions=True)
		return plan, objective, key_result, action

	def rename_all(self, hierarchy):
		for doc, fieldname in zip(
			reversed(hierarchy),
			("action_item_title", "key_result_title", "objective_title", "plan_name"),
			strict=True,
		):
			doc.set(fieldname, doc.get(fieldname) + " Renamed")
			doc.save(ignore_permissions=True)

	def assert_all_renames_blocked(self, hierarchy):
		for doc, fieldname in zip(
			hierarchy,
			("plan_name", "objective_title", "key_result_title", "action_item_title"),
			strict=True,
		):
			doc.reload()
			doc.set(fieldname, doc.get(fieldname) + " Blocked")
			with self.assertRaises(frappe.ValidationError):
				doc.save(ignore_permissions=True)

	def test_before_plan_start_all_titles_can_be_renamed(self):
		hierarchy = self.make_hierarchy(add_days(today(), 1))
		self.rename_all(hierarchy)

	def test_on_plan_start_all_title_renames_are_blocked(self):
		self.assert_all_renames_blocked(self.make_hierarchy(today()))

	def test_after_plan_start_all_title_renames_are_blocked(self):
		self.assert_all_renames_blocked(self.make_hierarchy(add_days(today(), -1)))

	def test_before_plan_start_document_id_can_be_renamed(self):
		_plan, _objective, _key_result, action = self.make_hierarchy(add_days(today(), 1))
		new_name = action.name + "-RENAMED"
		self.assertEqual(frappe.rename_doc(action.doctype, action.name, new_name), new_name)

	def test_on_plan_start_all_document_id_renames_are_blocked(self):
		for doc in self.make_hierarchy(today()):
			with self.subTest(doctype=doc.doctype):
				with self.assertRaises(frappe.ValidationError):
					frappe.rename_doc(doc.doctype, doc.name, doc.name + "-BLOCKED")

	def test_future_plan_cannot_rename_while_moving_start_to_today(self):
		plan, _objective, _key_result, _action = self.make_hierarchy(add_days(today(), 1))
		plan.plan_name += " Blocked"
		plan.planned_activation_date = today()
		with self.assertRaises(frappe.ValidationError):
			plan.save(ignore_permissions=True)

	def test_started_plan_date_cannot_be_postponed_to_unlock_title(self):
		plan, _objective, _key_result, _action = self.make_hierarchy(today())
		plan.planned_activation_date = add_days(today(), 1)
		with self.assertRaises(frappe.ValidationError):
			plan.save(ignore_permissions=True)

		plan.reload()
		plan.plan_name += " Still Blocked"
		with self.assertRaises(frappe.ValidationError):
			plan.save(ignore_permissions=True)

	def test_checkin_runtime_progress_update_remains_allowed(self):
		plan, _objective, key_result, action = self.make_hierarchy(today())
		plan.status = "Active"
		plan.save(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "OKR Check In",
				"action_item": action.name,
				"current_value": 40,
				"achievements": "Runtime progress remains available.",
				"action_status": "In Progress",
			}
		).insert(ignore_permissions=True)
		action.reload()
		key_result.reload()
		self.assertEqual(action.current_value, 40)
		self.assertEqual(action.progress, 40)
		self.assertEqual(key_result.current_value, 40)
		self.assertEqual(key_result.target_progress, 40)
