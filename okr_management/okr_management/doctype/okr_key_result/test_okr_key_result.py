from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from okr_management.utils.okr_calculations import recalculate_key_result_progress


class TestOKRKeyResult(FrappeTestCase):
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
				"plan_name": "KR Test " + frappe.generate_hash(length=6),
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
				"objective_title": "KR Objective " + frappe.generate_hash(length=6),
				"parent_plan": self.plan.name,
				"level": "Department",
				"level_details": self.department,
				"department": self.department,
				"owner_user": "Administrator",
				"status": "Draft",
			}
		).insert(ignore_permissions=True)

		self.user_action_assignee = self.make_test_user("actionassignee", ["Employee", "OKR User"])
		self.user_creator_only = self.make_test_user("creatoronly", ["Employee", "OKR User"])
		self.user_other_kr = self.make_test_user("otherkr", ["Employee", "OKR User"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_test_user(self, prefix: str, roles: list[str]) -> str:
		email = f"test.kr.{prefix}@example.com"
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Test",
					"last_name": prefix,
					"enabled": 1,
					"roles": [{"role": r} for r in roles],
				}
			).insert(ignore_permissions=True)
		else:
			user = frappe.get_doc("User", email)
			current = {r.role for r in user.roles}
			for r in roles:
				if r not in current:
					user.append("roles", {"role": r})
			user.save(ignore_permissions=True)
		return email

	def make_kr(self, **values):
		payload = {
			"doctype": "OKR Key Result",
			"key_result_title": "KR Test " + frappe.generate_hash(length=6),
			"objective": self.objective.name,
			"assignee": "Administrator",
			"metric_type": "Number",
			"metric_direction": "Increase",
			"calculation_mode": "Manual",
			"baseline_value": 0,
			"current_value": 25,
			"target_value": 100,
			"end_date": self.objective.end_date,
			"status": "Draft",
		}
		payload.update(values)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def make_action(self, kr, progress=0, due_date=None, assigned_to="Administrator", status="Open"):
		return frappe.get_doc(
			{
				"doctype": "OKR Action Item",
				"action_item_title": "KR Action " + frappe.generate_hash(length=6),
				"parent_key_result": kr.name,
				"assigned_to": assigned_to,
				"due_date": due_date or kr.end_date,
				"progress": progress,
				"status": status,
			}
		).insert(ignore_permissions=True)

	def test_timeline_is_inherited_from_objective(self):
		kr = self.make_kr(end_date=None)
		self.assertEqual(getdate(kr.start_date), getdate(self.objective.start_date))
		self.assertEqual(getdate(kr.end_date), getdate(self.objective.end_date))

		# Target Date (end_date) can be manually edited and persists within Objective bounds
		new_target = add_days(self.objective.start_date, 20)
		kr.end_date = new_target
		kr.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(getdate(kr.end_date), getdate(new_target))

	def test_action_due_date_uses_full_objective_timeline(self):
		kr = self.make_kr()
		action = self.make_action(kr, due_date=self.objective.start_date)
		self.assertEqual(getdate(action.due_date), getdate(self.objective.start_date))
		self.assertRaises(
			frappe.ValidationError,
			self.make_action,
			kr,
			due_date=add_days(self.objective.end_date, 1),
		)

	def test_measurement_progress_increase_and_decrease(self):
		self.assertEqual(self.make_kr(current_value=40).target_progress, 40)
		self.assertEqual(
			self.make_kr(
				baseline_value=10, current_value=6, target_value=2, metric_direction="Decrease"
			).target_progress,
			50,
		)

	def test_manual_metric_value_remains_authoritative_with_actions(self):
		kr = self.make_kr(current_value=25)
		self.make_action(kr, 20)
		self.make_action(kr, 80)
		recalculate_key_result_progress(kr.name)
		kr.reload()
		self.assertEqual(kr.target_progress, 25)
		self.assertEqual(kr.current_value, 25)

	def test_assignee_is_canonical_owner(self):
		kr = self.make_kr()
		self.assertEqual(kr.owner_user, kr.assignee)

	def test_kr_post_save_dates_and_values_persist(self):
		kr = self.make_kr(
			end_date=self.objective.end_date,
			target_value=100,
			status="Draft",
		)
		self.assertEqual(getdate(kr.end_date), getdate(self.objective.end_date))
		self.assertEqual(kr.target_value, 100)

		# Change Target Date (end_date) and Target Value, Save, Reload
		new_target_date = add_days(self.objective.start_date, 20)
		kr.end_date = new_target_date
		kr.target_value = 120
		kr.key_result_title = "KR Updated " + frappe.generate_hash(length=4)
		kr.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(getdate(kr.end_date), getdate(new_target_date))
		self.assertEqual(kr.target_value, 120)

		# Edit again after second save
		kr.target_value = 150
		kr.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(kr.target_value, 150)

	def test_invalid_kr_dates_rejected(self):
		kr = self.make_kr()
		kr.end_date = add_days(self.objective.end_date, 10)
		self.assertRaises(frappe.ValidationError, kr.save, ignore_permissions=True)

	def test_default_checkbox_is_checked(self):
		kr = self.make_kr()
		self.assertEqual(kr.lock_measurement_fields_for_action_item_assignees, 1)

	def test_action_item_assignee_cannot_modify_parent_kr(self):
		kr = self.make_kr(lock_measurement_fields_for_action_item_assignees=0, target_value=100)
		self.make_action(kr, assigned_to=self.user_action_assignee)
		frappe.set_user(self.user_action_assignee)
		kr_doc = frappe.get_doc("OKR Key Result", kr.name)
		kr_doc.target_value = 200
		self.assertRaises(frappe.PermissionError, kr_doc.save)

	def test_full_write_owner_admin_behavior_unchanged(self):
		kr = self.make_kr(assignee="Administrator", metric_type="Number", target_value=100)
		frappe.set_user("Administrator")
		kr_doc = frappe.get_doc("OKR Key Result", kr.name)
		kr_doc.metric_type = "Percentage"
		kr_doc.target_value = 150
		kr_doc.save()
		kr_doc.reload()
		self.assertEqual(kr_doc.metric_type, "Percentage")
		self.assertEqual(kr_doc.target_value, 150)

	def test_measurement_lock_checkbox_placed_below_goal_direction(self):
		meta = frappe.get_meta("OKR Key Result")
		field_order = [f.fieldname for f in meta.fields]
		direction_idx = field_order.index("metric_direction")
		lock_idx = field_order.index("lock_measurement_fields_for_action_item_assignees")
		self.assertGreater(lock_idx, direction_idx)
		self.assertEqual(meta.get_field("lock_measurement_fields_for_action_item_assignees").default, "1")
