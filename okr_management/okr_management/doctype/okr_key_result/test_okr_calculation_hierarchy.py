import frappe

from okr_management.okr_management.doctype.okr_key_result.test_okr_key_result import (
	TestOKRKeyResult,
)
from okr_management.utils.okr_calculations import recalculate_key_result_progress


class TestOKRCalculationHierarchy(TestOKRKeyResult):
	def make_automatic_kr(self):
		return self.make_kr(
			calculation_mode="Automatic",
			current_value=0,
			baseline_value=0,
			target_value=100,
		)

	def set_action_value(self, action, value):
		frappe.db.set_value("OKR Action Item", action.name, "current_value", value)
		recalculate_key_result_progress(action.parent_key_result)

	def test_zero_no_checkin_archive_and_order_independence(self):
		kr = self.make_automatic_kr()
		a = self.make_action(kr)
		b = self.make_action(kr)

		self.set_action_value(a, 100)
		kr.reload()
		self.assertEqual(kr.target_progress, 50)

		# B has no Check-In; its legitimate zero remains in the denominator.
		self.assertFalse(frappe.db.exists("OKR Check In", {"action_item": b.name}))
		self.assertEqual(kr.target_progress, 50)

		b.status = "Done"
		b.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(kr.target_progress, 100)

		b.status = "Open"
		b.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(kr.target_progress, 50)

	def test_latest_checkin_never_replaces_automatic_kr_aggregate(self):
		kr = self.make_automatic_kr()
		a = self.make_action(kr)
		b = self.make_action(kr)

		for action, current in ((a, 100), (b, 0)):
			frappe.get_doc(
				{
					"doctype": "OKR Check In",
					"action_item": action.name,
					"current_value": current,
					"action_status": "In Progress",
					"achievements": "Calculation regression",
				}
			).insert(ignore_permissions=True)
			kr.reload()
			self.assertEqual(kr.target_progress, 50)
			self.assertEqual(kr.current_value, 50)

	def test_stale_automatic_parent_recalculates_after_every_child_change_and_api_matches(self):
		from okr_management.okr_management.page.okr_workspace.okr_workspace import get_key_results

		kr = self.make_automatic_kr()
		a = self.make_action(kr)
		b = self.make_action(kr)
		# Model a previously persisted stale parent without invoking a recalculation.
		frappe.db.set_value("OKR Action Item", a.name, {"current_value": 0, "progress": 0})
		frappe.db.set_value("OKR Action Item", b.name, {"current_value": 79.17, "progress": 79.17})
		frappe.db.set_value("OKR Key Result", kr.name, "target_progress", 39.585)
		kr.reload()
		self.assertAlmostEqual(kr.target_progress, 39.585, places=3)

		b.reload()
		b.current_value = 0
		b.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(a.reload().progress, 0)
		self.assertEqual(b.reload().progress, 0)
		self.assertEqual(kr.target_progress, 0)
		self.assertEqual(kr.current_value, 0)
		api_kr = next(row for row in get_key_results([self.objective.name]) if row.name == kr.name)
		self.assertEqual(api_kr.target_progress, 0)
		self.assertEqual(api_kr.current_value, 0)

		a.current_value = 50
		a.save(ignore_permissions=True)
		kr.reload()
		self.assertEqual(kr.target_progress, 25)
		self.assertEqual(kr.current_value, 25)

		b.current_value = 50
		b.save(ignore_permissions=True)
		kr.reload()
		self.objective.reload()
		self.plan.reload()
		self.assertEqual(kr.target_progress, 50)
		self.assertEqual(kr.current_value, 50)
		self.assertEqual(self.objective.progress, 50)
		self.assertEqual(self.plan.progress, 50)

	def test_three_action_matrix_and_full_rollup(self):
		kr = self.make_automatic_kr()
		actions = [self.make_action(kr) for _ in range(3)]
		for action, value in zip(actions, (100, 50, 0), strict=True):
			self.set_action_value(action, value)

		objective_2 = frappe.copy_doc(self.objective)
		objective_2.objective_title = "Second Objective " + frappe.generate_hash(length=6)
		objective_2.insert(ignore_permissions=True)
		kr_2 = self.make_kr(objective=objective_2.name, calculation_mode="Automatic", current_value=0)
		action_c = self.make_action(kr_2)
		self.set_action_value(action_c, 50)

		kr.reload()
		self.objective.reload()
		objective_2.reload()
		kr_2.reload()
		self.plan.reload()
		self.assertEqual(kr.target_progress, 50)
		self.assertEqual(self.objective.progress, 50)
		self.assertEqual(kr_2.target_progress, 50)
		self.assertEqual(objective_2.progress, 50)
		self.assertEqual(self.plan.progress, 50)

	def test_objective_includes_zero_progress_key_results(self):
		self.make_kr(current_value=100)
		self.make_kr(current_value=0)
		self.objective.reload()
		self.assertEqual(self.objective.progress, 50)

	def test_objective_three_key_result_average(self):
		for value in (100, 50, 0):
			self.make_kr(current_value=value)
		self.objective.reload()
		self.assertEqual(self.objective.progress, 50)

	def test_plan_includes_zero_progress_objective(self):
		self.make_kr(current_value=100)
		objective_2 = frappe.copy_doc(self.objective)
		objective_2.objective_title = "Zero Objective " + frappe.generate_hash(length=6)
		objective_2.insert(ignore_permissions=True)
		self.make_kr(objective=objective_2.name, current_value=0)
		self.plan.reload()
		self.assertEqual(self.plan.progress, 50)

	def test_legacy_archived_action_is_excluded_displayed_as_done_and_normalized_on_save(self):
		from okr_management.okr_management.page.okr_workspace.okr_workspace import get_action_items

		kr = self.make_automatic_kr()
		a = self.make_action(kr)
		b = self.make_action(kr)
		self.set_action_value(a, 100)
		frappe.db.set_value("OKR Action Item", b.name, "status", "Archived")
		recalculate_key_result_progress(kr.name)
		kr.reload()
		self.assertEqual(kr.target_progress, 100)

		rows = {row.name: row for row in get_action_items([kr.name])}
		self.assertEqual(rows[b.name].status, "Done")

		b.reload()
		b.save(ignore_permissions=True)
		b.reload()
		self.assertEqual(b.status, "Done")
