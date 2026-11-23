from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from okr_management.utils.okr_calculations import (
	average,
	calculate_metric_progress,
	get_key_result_progress,
)


class TestOKRCalculations(FrappeTestCase):
	def test_metric_matrix(self):
		cases = [
			("percentage increase zero", 0, 0, 100, "Increase", "Percentage", 0),
			("percentage increase target", 0, 100, 100, "Increase", "Percentage", 100),
			("percentage increase capped", 0, 125, 100, "Increase", "Percentage", 100),
			("percentage increase below start", 0, -10, 100, "Increase", "Percentage", 0),
			("percentage decrease", 100, 60, 20, "Decrease", "Percentage", 50),
			("number increase", 20, 60, 100, "Increase", "Number", 50),
			("number decrease", 100, 60, 20, "Decrease", "Number", 50),
			("currency increase", 0, 40, 100, "Increase", "Currency", 40),
			("currency decrease", 100, 60, 20, "Decrease", "Currency", 50),
			("currency decrease at target", 100000, 10, 10, "Decrease", "Currency", 100),
			("currency decrease below target is invalid", 100000, 0, 10, "Decrease", "Currency", 0),
			("equal endpoints", 10, 10, 10, "Increase", "Number", 0),
			("negative range", -100, -50, 0, "Increase", "Number", 50),
		]
		for label, start, current, target, direction, metric_type, expected in cases:
			with self.subTest(label=label):
				self.assertEqual(
					calculate_metric_progress(start, current, target, direction, metric_type),
					expected,
				)

	def test_numeric_zero_representations_are_real_values(self):
		for zero in (0, 0.0, Decimal("0")):
			with self.subTest(zero=repr(zero)):
				self.assertEqual(calculate_metric_progress(0, zero, 100), 0)
		self.assertEqual(average([100, 0]), 50)
		self.assertEqual(average([100, 50, 0]), 50)
		self.assertEqual(average([0, 0]), 0)

	def test_automatic_kr_averages_every_non_archived_action_order_independently(self):
		kr = {
			"calculation_mode": "Automatic",
			"metric_type": "Percentage",
			"metric_direction": "Increase",
			"baseline_value": 0,
			"current_value": 0,
			"target_value": 100,
		}
		def action(name, current):
			return {
				"name": name, "progress": current, "current_value": current,
				"customize_measurement": 0, "metric_type": "Percentage",
				"metric_direction": "Increase", "baseline_value": 0, "target_value": 100,
			}

		for values, expected in [
			([action("A", 100), action("B", 0)], 50),
			([action("B", 0), action("A", 100)], 50),
			([action("A", 100), action("B", 50), action("C", 0)], 50),
			([action("A", 20), action("B", 40), action("C", 60)], 40),
			([action("A", 100)], 100),
		]:
			with self.subTest(values=values):
				checkins = [
					{"action_item": item["name"], "current_value": item["current_value"], "progress": item["progress"]}
					for item in values
				]
				with patch("okr_management.utils.okr_calculations.frappe.get_all", side_effect=[values, checkins]), patch(
					"okr_management.utils.okr_calculations.frappe.db.set_value"
				):
					self.assertEqual(get_key_result_progress("KR-1", kr), expected)

	def test_manual_kr_uses_children_when_present_and_own_metric_only_without_children(self):
		kr = {
			"calculation_mode": "Manual", "metric_type": "Number",
			"metric_direction": "Increase", "baseline_value": 0,
			"current_value": 40, "target_value": 100,
		}
		actions = [
			{"name": "A", "progress": 90, "current_value": 90, "customize_measurement": 1,
			 "metric_type": "Percentage", "metric_direction": "Increase", "baseline_value": 0, "target_value": 100},
			{"name": "B", "progress": 79.99, "current_value": 79.99, "customize_measurement": 1,
			 "metric_type": "Percentage", "metric_direction": "Increase", "baseline_value": 0, "target_value": 100},
		]
		checkins = [
			{"action_item": item["name"], "current_value": item["current_value"], "progress": item["progress"]}
			for item in actions
		]
		with patch("okr_management.utils.okr_calculations.frappe.get_all", side_effect=[actions, checkins]), patch(
			"okr_management.utils.okr_calculations.frappe.db.set_value"
		):
			self.assertEqual(get_key_result_progress("KR-1", kr), 85.0)

		with patch("okr_management.utils.okr_calculations.frappe.get_all", return_value=[]):
			self.assertEqual(get_key_result_progress("KR-1", kr), 40)

	def test_rollup_averages_include_zero(self):
		self.assertEqual(average([100, 0]), 50)
		self.assertEqual(average([100, 50, 0]), 50)
		self.assertEqual(average([50, 50]), 50)

	def test_action_without_checkin_is_zero_and_latest_checkin_wins(self):
		kr = {"metric_type": "Percentage", "baseline_value": 0, "current_value": 0, "target_value": 100}
		actions = [
			frappe._dict({"name": "A", "progress": 99, "current_value": 99}),
			frappe._dict({"name": "B", "progress": 88, "current_value": 88}),
		]
		checkins = [
			{"action_item": "A", "current_value": 30, "progress": 30},
			{"action_item": "A", "current_value": 20, "progress": 20},
			{"action_item": "A", "current_value": 10, "progress": 10},
		]
		with patch(
			"okr_management.utils.okr_calculations.frappe.get_all", side_effect=[actions, checkins]
		), patch("okr_management.utils.okr_calculations.frappe.db.set_value") as set_value:
			self.assertEqual(get_key_result_progress("KR-1", kr), 15)
		b_update = next(call.args[2] for call in set_value.call_args_list if call.args[1] == "B")
		self.assertEqual(b_update, {"progress": 0.0})

	def test_three_action_latest_checkin_matrix(self):
		kr = {"metric_type": "Percentage", "baseline_value": 0, "current_value": 0, "target_value": 100}
		actions = [frappe._dict({"name": name, "progress": 0, "current_value": 0}) for name in "ABC"]
		for progress_by_action, expected in [({"A": 30, "B": 20, "C": 40}, 30), ({"A": 30, "C": 40}, 23.33)]:
			checkins = [
				{"action_item": name, "current_value": value, "progress": value}
				for name, value in progress_by_action.items()
			]
			with patch(
				"okr_management.utils.okr_calculations.frappe.get_all", side_effect=[actions, checkins]
			), patch("okr_management.utils.okr_calculations.frappe.db.set_value"):
				self.assertEqual(get_key_result_progress("KR-1", kr), expected)

	def test_latest_checkins_are_prefetched_once_for_all_actions(self):
		kr = {
			"metric_type": "Percentage",
			"metric_direction": "Increase",
			"baseline_value": 0,
			"current_value": 0,
			"target_value": 100,
		}
		actions = [
			frappe._dict({"name": "A", "progress": 10, "current_value": 10}),
			frappe._dict({"name": "B", "progress": 20, "current_value": 20}),
		]
		checkins = [
			{"action_item": "A", "current_value": 70, "progress": 70},
			{"action_item": "A", "current_value": 30, "progress": 30},
			{"action_item": "B", "current_value": 30, "progress": 30},
		]
		with patch(
			"okr_management.utils.okr_calculations.frappe.get_all",
			side_effect=[actions, checkins],
		) as get_all, patch(
			"okr_management.utils.okr_calculations.frappe.db.get_value"
		) as get_value, patch(
			"okr_management.utils.okr_calculations.frappe.db.set_value"
		):
			self.assertEqual(get_key_result_progress("KR-1", kr), 50)

		self.assertEqual(get_all.call_count, 2)
		get_value.assert_not_called()
