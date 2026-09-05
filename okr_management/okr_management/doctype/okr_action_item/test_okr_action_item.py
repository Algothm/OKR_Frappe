from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, today

from okr_management.okr_management.page.okr_workspace.okr_workspace import save_workspace_checkin, get_action_items, get_workspace_data


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
				"metric_type": "Currency",
				"metric_direction": "Increase",
				"baseline_value": 0,
				"current_value": 0,
				"target_value": 100000,
				"calculation_mode": "Automatic",
				"end_date": self.objective.end_date,
				"lock_measurement_fields_for_action_item_assignees": 1,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)

		self.user_a = self.make_test_user("usera")
		self.user_b = self.make_test_user("userb")
		self.user_c = self.make_test_user("userc")

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_test_user(self, prefix: str) -> str:
		email = f"test.ai.{prefix}@example.com"
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Test",
					"last_name": prefix,
					"enabled": 1,
					"roles": [{"role": "Employee"}, {"role": "OKR User"}],
				}
			).insert(ignore_permissions=True)
		else:
			user = frappe.get_doc("User", email)
			current = {r.role for r in user.roles}
			for r in ["Employee", "OKR User"]:
				if r not in current:
					user.append("roles", {"role": r})
			user.save(ignore_permissions=True)
		if not frappe.db.exists("Employee", {"user_id": email}):
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "Test",
					"last_name": prefix,
					"user_id": email,
					"company": self.company,
					"status": "Active",
					"gender": "Female",
					"date_of_birth": "1990-01-01",
					"date_of_joining": "2020-01-01",
				}
			).insert(ignore_permissions=True)
		return email

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

	def test_action_item_post_save_fields_persist(self):
		action = self.make_action(due_date=self.kr.end_date)
		self.assertEqual(getdate(action.due_date), getdate(self.kr.end_date))

	# === 12 FOCUSED VALIDATION TESTS FOR MEASUREMENT CUSTOMIZATION ===

	def test_1_kr_locked_blocks_own_ai_customization(self):
		# 1. KR locked -> own AI customization DENIED.
		self.kr.lock_measurement_fields_for_action_item_assignees = 1
		self.kr.save(ignore_permissions=True)

		action = self.make_action(assigned_to=self.user_a)
		frappe.set_user(self.user_a)
		ai_doc = frappe.get_doc("OKR Action Item", action.name)
		ai_doc.customize_measurement = 1
		ai_doc.metric_type = "Percentage"
		ai_doc.target_value = 50
		self.assertRaises(frappe.PermissionError, ai_doc.save)

	def test_2_kr_unlocked_allows_own_ai_customization(self):
		# 2. KR unlocked -> own AI customization PASS.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		action = self.make_action(assigned_to=self.user_a)
		frappe.set_user(self.user_a)
		ai_doc = frappe.get_doc("OKR Action Item", action.name)
		ai_doc.customize_measurement = 1
		ai_doc.metric_type = "Percentage"
		ai_doc.metric_direction = "Increase"
		ai_doc.baseline_value = 0
		ai_doc.target_value = 50
		ai_doc.save()
		ai_doc.reload()
		self.assertEqual(ai_doc.customize_measurement, 1)
		self.assertEqual(ai_doc.metric_type, "Percentage")
		self.assertEqual(ai_doc.target_value, 50)

	def test_3_and_4_parent_kr_and_sibling_ai_remain_unchanged(self):
		# 3. Parent KR unchanged.
		# 4. Sibling AI unchanged.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		ai_1 = self.make_action(assigned_to=self.user_a)
		ai_2 = self.make_action(assigned_to=self.user_b)
		ai_3 = self.make_action(assigned_to=self.user_c)

		# Initially all inherit parent KR
		self.assertEqual(ai_1.metric_type, "Currency")
		self.assertEqual(ai_2.metric_type, "Currency")
		self.assertEqual(ai_3.metric_type, "Currency")

		# User B customizes AI-2
		frappe.set_user(self.user_b)
		ai_2_doc = frappe.get_doc("OKR Action Item", ai_2.name)
		ai_2_doc.customize_measurement = 1
		ai_2_doc.metric_type = "Percentage"
		ai_2_doc.baseline_value = 0
		ai_2_doc.target_value = 100
		ai_2_doc.save()

		# Assertions:
		self.kr.reload()
		self.assertEqual(self.kr.metric_type, "Currency")
		self.assertEqual(self.kr.target_value, 100000)

		ai_1.reload()
		self.assertEqual(ai_1.customize_measurement, 0)
		self.assertEqual(ai_1.metric_type, "Currency")
		self.assertEqual(ai_1.target_value, 100000)

		ai_3.reload()
		self.assertEqual(ai_3.customize_measurement, 0)
		self.assertEqual(ai_3.metric_type, "Currency")
		self.assertEqual(ai_3.target_value, 100000)

		ai_2_doc.reload()
		self.assertEqual(ai_2_doc.customize_measurement, 1)
		self.assertEqual(ai_2_doc.metric_type, "Percentage")
		self.assertEqual(ai_2_doc.target_value, 100)

	def test_5_same_user_with_two_ais_independent_customization(self):
		# 5. Same user with two AIs -> independent customization.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		ai_a1 = self.make_action(assigned_to=self.user_a)
		ai_a2 = self.make_action(assigned_to=self.user_a)

		frappe.set_user(self.user_a)
		doc_1 = frappe.get_doc("OKR Action Item", ai_a1.name)
		doc_1.customize_measurement = 1
		doc_1.metric_type = "Number"
		doc_1.baseline_value = 10
		doc_1.target_value = 200
		doc_1.save()

		doc_2 = frappe.get_doc("OKR Action Item", ai_a2.name)
		self.assertEqual(doc_2.customize_measurement, 0)
		self.assertEqual(doc_2.metric_type, "Currency")
		self.assertEqual(doc_2.target_value, 100000)

	def test_6_user_a_cannot_edit_user_b_ai_customization(self):
		# 6. User A cannot edit User B's AI customization.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		ai_b = self.make_action(assigned_to=self.user_b)

		frappe.set_user(self.user_a)
		ai_b_doc = frappe.get_doc("OKR Action Item", ai_b.name)
		ai_b_doc.customize_measurement = 1
		ai_b_doc.target_value = 999
		self.assertRaises(frappe.PermissionError, ai_b_doc.save)

	def test_7_and_8_customize_toggle_inherits_or_uses_own_fields(self):
		# 7. Customize OFF -> inherits KR.
		# 8. Customize ON -> uses own 5-field measurement.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		action = self.make_action(assigned_to=self.user_a)
		self.assertEqual(action.customize_measurement, 0)
		self.assertEqual(action.metric_type, self.kr.metric_type)
		self.assertEqual(action.target_value, self.kr.target_value)

		frappe.set_user(self.user_a)
		ai_doc = frappe.get_doc("OKR Action Item", action.name)
		ai_doc.customize_measurement = 1
		ai_doc.metric_type = "Percentage"
		ai_doc.metric_direction = "Decrease"
		ai_doc.baseline_value = 100
		ai_doc.target_value = 10
		ai_doc.save()

		ai_doc.reload()
		self.assertEqual(ai_doc.metric_type, "Percentage")
		self.assertEqual(ai_doc.metric_direction, "Decrease")
		self.assertEqual(ai_doc.baseline_value, 100)
		self.assertEqual(ai_doc.target_value, 10)

		# Turn OFF again -> inherits KR
		ai_doc.customize_measurement = 0
		ai_doc.save()
		ai_doc.reload()
		self.assertEqual(ai_doc.metric_type, "Currency")
		self.assertEqual(ai_doc.target_value, 100000)

	def test_9_relock_blocks_further_editing_but_keeps_stored_values(self):
		# 9. Re-lock -> further editing denied.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		action = self.make_action(assigned_to=self.user_a)
		frappe.set_user(self.user_a)
		ai_doc = frappe.get_doc("OKR Action Item", action.name)
		ai_doc.customize_measurement = 1
		ai_doc.metric_type = "Percentage"
		ai_doc.target_value = 75
		ai_doc.save()

		# Owner re-locks KR
		frappe.set_user("Administrator")
		self.kr.lock_measurement_fields_for_action_item_assignees = 1
		self.kr.save(ignore_permissions=True)

		# Values remain stored
		action.reload()
		self.assertEqual(action.customize_measurement, 1)
		self.assertEqual(action.target_value, 75)

		# User A tries to edit customization -> DENIED
		frappe.set_user(self.user_a)
		ai_doc = frappe.get_doc("OKR Action Item", action.name)
		ai_doc.target_value = 90
		self.assertRaises(frappe.PermissionError, ai_doc.save)

	def test_10_workspace_and_checkin_uses_effective_ai_measurement(self):
		# 10. Workspace/Check-In uses effective AI measurement.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		action = self.make_action(assigned_to=self.user_a)
		frappe.set_user(self.user_a)
		ai_doc = frappe.get_doc("OKR Action Item", action.name)
		ai_doc.customize_measurement = 1
		ai_doc.metric_type = "Percentage"
		ai_doc.metric_direction = "Increase"
		ai_doc.baseline_value = 0
		ai_doc.target_value = 100
		ai_doc.save()

		# Check-in via save_workspace_checkin
		res = save_workspace_checkin(
			action_item=action.name,
			current_value=60,
			update="Testing custom check-in",
			status="In Progress",
		)
		self.assertIsNotNone(res.get("name"))

		action.reload()
		self.assertEqual(action.current_value, 60)
		self.assertEqual(action.progress, 60)

		# Parent KR current_value must NOT be overwritten with 60
		self.kr.reload()
		self.assertEqual(self.kr.current_value, 0)
		# Parent KR target_progress reflects average of its action items (60%)
		self.assertEqual(self.kr.target_progress, 60)

	def test_11_existing_action_items_without_customization_behave_as_before(self):
		# 11. Existing Action Items without customization behave exactly as before.
		action = self.make_action(assigned_to=self.user_a)
		frappe.set_user(self.user_a)
		res = save_workspace_checkin(
			action_item=action.name,
			current_value=25000,
			update="Inherited KR measurement checkin",
			status="In Progress",
		)
		self.assertIsNotNone(res.get("name"))

		action.reload()
		self.assertEqual(action.progress, 25.0)

		self.kr.reload()
		self.assertEqual(self.kr.current_value, 25000)
		self.assertEqual(self.kr.target_progress, 25.0)

	def test_12_no_parent_kr_delegated_write_permission_remains(self):
		# 12. No parent KR delegated write permission remains.
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		self.make_action(assigned_to=self.user_a)
		frappe.set_user(self.user_a)

		kr_doc = frappe.get_doc("OKR Key Result", self.kr.name)
		kr_doc.target_value = 200000
		self.assertRaises(frappe.PermissionError, kr_doc.save)

	def test_13_focused_custom_current_value_and_workspace_mixed_units(self):
		"""Test all 12 specific requirements from the user prompt."""
		# Setup parent KR as Number 2 / 5
		self.kr.metric_type = "Number"
		self.kr.metric_direction = "Increase"
		self.kr.baseline_value = 0
		self.kr.target_value = 5
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)
		frappe.db.set_value("OKR Key Result", self.kr.name, "current_value", 2)

		# 1. Custom measurement ON: assigned user can edit current_value. Save + reload persists.
		# 4. Custom Percentage: Start 20, Target 100, Current 40 -> expected normalized completion = 25%.
		ai_2 = self.make_action(assigned_to=self.user_b)
		frappe.set_user(self.user_b)
		ai_2_doc = frappe.get_doc("OKR Action Item", ai_2.name)
		ai_2_doc.customize_measurement = 1
		ai_2_doc.metric_type = "Percentage"
		ai_2_doc.metric_direction = "Increase"
		ai_2_doc.baseline_value = 20
		ai_2_doc.target_value = 100
		ai_2_doc.current_value = 40
		ai_2_doc.save()

		ai_2_doc.reload()
		self.assertEqual(ai_2_doc.current_value, 40)
		self.assertEqual(ai_2_doc.progress, 25.0)

		# 2. Lock CHECKED: current_value customization denied.
		frappe.set_user("Administrator")
		self.kr.reload()
		self.kr.lock_measurement_fields_for_action_item_assignees = 1
		self.kr.save(ignore_permissions=True)

		frappe.set_user(self.user_b)
		ai_locked_doc = frappe.get_doc("OKR Action Item", ai_2.name)
		ai_locked_doc.current_value = 45
		self.assertRaises(frappe.PermissionError, ai_locked_doc.save)

		# Unlock for subsequent multi-AI tests
		frappe.set_user("Administrator")
		self.kr.reload()
		self.kr.lock_measurement_fields_for_action_item_assignees = 0
		self.kr.save(ignore_permissions=True)

		# 3. Customize OFF: Action Item inherits KR measurement.
		ai_1 = self.make_action(assigned_to=self.user_a)
		self.assertEqual(ai_1.customize_measurement, 0)
		self.assertEqual(ai_1.metric_type, "Number")
		self.assertEqual(ai_1.baseline_value, 0)
		self.assertEqual(ai_1.target_value, 5)

		# AI-3: custom Currency 0 -> 100000, current 50000, completion = 50%
		ai_3 = self.make_action(assigned_to=self.user_c)
		frappe.set_user(self.user_c)
		ai_3_doc = frappe.get_doc("OKR Action Item", ai_3.name)
		ai_3_doc.customize_measurement = 1
		ai_3_doc.metric_type = "Currency"
		ai_3_doc.metric_direction = "Increase"
		ai_3_doc.baseline_value = 0
		ai_3_doc.target_value = 100000
		ai_3_doc.current_value = 50000
		ai_3_doc.save()
		ai_3_doc.reload()
		self.assertEqual(ai_3_doc.progress, 50.0)

		# AI-1 (inherits KR Number 0 -> 5): check-in to current 1 (completion 20%)
		frappe.set_user(self.user_a)
		save_workspace_checkin(
			action_item=ai_1.name,
			current_value=1,
			update="AI 1 check-in",
			status="In Progress",
		)
		ai_1.reload()
		self.assertEqual(ai_1.progress, 20.0)

		# 5. Workspace displays that Action Item's 25% progress.
		ws_items = get_action_items([self.kr.name])
		ws_map = {item["name"]: item for item in ws_items}
		self.assertEqual(ws_map[ai_2.name]["progress"], 25.0)
		self.assertEqual(ws_map[ai_3.name]["progress"], 50.0)
		self.assertEqual(ws_map[ai_1.name]["progress"], 20.0)

		# 6. Parent KR remains Number 2 / 5 canonical measurement.
		# 12. Parent KR canonical measurement fields are not modified by AI updates.
		self.kr.reload()
		self.assertEqual(self.kr.metric_type, "Number")
		self.assertEqual(self.kr.baseline_value, 0)
		self.assertEqual(self.kr.target_value, 5)
		# 11. Mixed-unit child progress aggregates normalized %: (20% + 25% + 50%) / 3 = 31.67%
		# Never aggregates raw values (₹50000 + 40% + 1 unit)
		self.assertEqual(self.kr.target_progress, 31.67)

		# 7. Sibling Action Items remain unchanged when one is modified.
		# 8. Different Action Items under same KR simultaneously use Number, Percentage, Currency.
		# 9. Their progress is calculated independently.
		ai_1.reload()
		ai_2_doc.reload()
		ai_3_doc.reload()
		self.assertEqual(ai_1.metric_type, "Number")
		self.assertEqual(ai_2_doc.metric_type, "Percentage")
		self.assertEqual(ai_3_doc.metric_type, "Currency")
		self.assertEqual(ai_1.progress, 20.0)
		self.assertEqual(ai_2_doc.progress, 25.0)
		self.assertEqual(ai_3_doc.progress, 50.0)

		# 10. Check-In uses the exact Action Item effective measurement.
		frappe.set_user(self.user_b)
		save_workspace_checkin(
			action_item=ai_2.name,
			current_value=60, # for 20->100, 60 is (60-20)/(100-20)*100 = 50%
			update="AI-2 updated to 60",
			status="In Progress",
		)
		ai_2_doc.reload()
		self.assertEqual(ai_2_doc.current_value, 60)
		self.assertEqual(ai_2_doc.progress, 50.0)
		# Parent KR canonical measurement fields remain unchanged
		self.kr.reload()
		self.assertEqual(self.kr.metric_type, "Number")
		self.assertEqual(self.kr.baseline_value, 0)
		self.assertEqual(self.kr.target_value, 5)
