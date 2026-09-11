from decimal import Decimal
from unittest.mock import patch

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
				with patch("okr_management.utils.okr_calculations.frappe.get_all", return_value=values), patch(
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
		with patch("okr_management.utils.okr_calculations.frappe.get_all", return_value=actions), patch(
			"okr_management.utils.okr_calculations.frappe.db.set_value"
		):
			self.assertEqual(get_key_result_progress("KR-1", kr), 85.0)

		with patch("okr_management.utils.okr_calculations.frappe.get_all", return_value=[]):
			self.assertEqual(get_key_result_progress("KR-1", kr), 40)

	def test_rollup_averages_include_zero(self):
		self.assertEqual(average([100, 0]), 50)
		self.assertEqual(average([100, 50, 0]), 50)
		self.assertEqual(average([50, 50]), 50)
