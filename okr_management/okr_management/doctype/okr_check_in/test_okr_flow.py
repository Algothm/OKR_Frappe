import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate, flt

class TestOKRFlow(FrappeTestCase):
	def setUp(self):
		# Clean transactions to avoid collision
		frappe.db.delete("OKR Check In")
		frappe.db.delete("OKR Key Result")
		frappe.db.delete("OKR Objective")
		frappe.db.delete("OKR Cycle")
		
		# Ensure default company
		if not frappe.db.exists("Company", "Test Company"):
			self.company = frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Company",
				"abbr": "TC",
				"default_currency": "INR",
				"country": "India"
			}).insert(ignore_permissions=True)
			
		# Create test cycle
		self.cycle = frappe.get_doc({
			"doctype": "OKR Cycle",
			"cycle_name": "Test Q1 Cycle",
			"company": "Test Company",
			"start_date": nowdate(),
			"end_date": add_days(nowdate(), 90),
			"status": "Active"
		})
		self.cycle.insert(ignore_permissions=True)

		# Create test objective
		self.objective = frappe.get_doc({
			"doctype": "OKR Objective",
			"objective_title": "Increase Revenue and efficiency",
			"cycle": self.cycle.name,
			"objective_type": "Company",
			"priority": "Strategic",
			"status": "Active"
		}).insert(ignore_permissions=True)

	def test_progress_calculation_increase(self):
		# Increase metric type key result
		kr = frappe.get_doc({
			"doctype": "OKR Key Result",
			"key_result_title": "Increase Sales deals",
			"objective": self.objective.name,
			"metric_type": "Count",
			"metric_direction": "Increase",
			"baseline_value": 10.0,
			"target_value": 50.0,
			"weight": 10.0,
			"approval_status": "Approved",
			"status": "Active"
		}).insert(ignore_permissions=True)

		# Check-in
		checkin = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 30.0,
			"confidence": "3",
			"status": "Submitted"
		})
		checkin.insert(ignore_permissions=True)

		self.assertEqual(checkin.progress, 50.0)
		self.assertEqual(checkin.progress_percent, 50.0)

		# Check parent KR synced values
		kr.reload()
		self.assertEqual(kr.current_value, 30.0)
		self.assertEqual(kr.target_progress, 50.0)
		self.assertEqual(kr.status, "Active")

	def test_progress_calculation_decrease(self):
		# Decrease metric direction key result
		kr = frappe.get_doc({
			"doctype": "OKR Key Result",
			"key_result_title": "Decrease Resolution Time",
			"objective": self.objective.name,
			"metric_type": "Count",
			"metric_direction": "Decrease",
			"baseline_value": 15.0,
			"target_value": 4.0,
			"weight": 10.0,
			"approval_status": "Approved",
			"status": "Active"
		}).insert(ignore_permissions=True)

		# Check-in
		checkin = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 9.5,
			"confidence": "3",
			"status": "Submitted"
		})
		checkin.insert(ignore_permissions=True)

		# ((15 - 9.5) / (15 - 4)) * 100 = 50.0%
		self.assertEqual(checkin.progress, 50.0)
		
		kr.reload()
		self.assertEqual(kr.current_value, 9.5)
		self.assertEqual(kr.target_progress, 50.0)

	def test_unapproved_kr_checkin_blocked(self):
		kr = frappe.get_doc({
			"doctype": "OKR Key Result",
			"key_result_title": "Pending KR",
			"objective": self.objective.name,
			"metric_type": "Percentage",
			"metric_direction": "Increase",
			"baseline_value": 0,
			"target_value": 100,
			"approval_status": "Draft",
			"status": "Draft"
		}).insert(ignore_permissions=True)

		checkin = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 10,
			"confidence": "3"
		})
		self.assertRaises(frappe.ValidationError, checkin.insert)

	def test_flexible_status_calculation(self):
		kr = frappe.get_doc({
			"doctype": "OKR Key Result",
			"key_result_title": "Flexible Status KR",
			"objective": self.objective.name,
			"metric_type": "Count",
			"metric_direction": "Increase",
			"baseline_value": 0,
			"target_value": 100,
			"approval_status": "Approved",
			"status": "Active"
		}).insert(ignore_permissions=True)

		# Case 1: High progress but low confidence triggers "At Risk"
		checkin1 = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 90.0,
			"confidence": "1",
			"status": "Submitted"
		}).insert(ignore_permissions=True)

		kr.reload()
		self.assertEqual(kr.status, "At Risk")

		# Ensure Department "HR" exists
		if not frappe.db.exists("Department", {"department_name": "HR", "company": "Test Company"}):
			dep = frappe.get_doc({
				"doctype": "Department", 
				"department_name": "HR", 
				"company": "Test Company",
				"is_group": 0
			}).insert(ignore_permissions=True)
			dep_name = dep.name
		else:
			dep_name = frappe.db.get_value("Department", {"department_name": "HR", "company": "Test Company"}, "name")

		# Case 2: High progress but Critical dependency triggers "Blocked"
		checkin2 = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 95.0,
			"confidence": "5",
			"has_dependency": 1,
			"dependent_department": dep_name,
			"dependency_description": "Budget pending",
			"impact_level": "Critical",
			"status": "Submitted"
		})
		checkin2.insert(ignore_permissions=True)

		kr.reload()
		self.assertEqual(kr.status, "Blocked")

	def test_employee_permission_restriction(self):
		user_email = "test.employee.perm@example.com"
		if not frappe.db.exists("User", user_email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": user_email,
				"first_name": "Test",
				"last_name": "Employee",
				"send_welcome_email": 0
			}).insert(ignore_permissions=True)
			user.add_roles("Employee")

		frappe.set_user(user_email)

		# Test cycle creation blocked
		new_cycle = frappe.get_doc({
			"doctype": "OKR Cycle",
			"cycle_name": "Unauthorized Cycle",
			"company": "Test Company",
			"start_date": nowdate(),
			"end_date": add_days(nowdate(), 30)
		})
		self.assertRaises(frappe.PermissionError, new_cycle.insert)

		# Test objective creation blocked
		new_objective = frappe.get_doc({
			"doctype": "OKR Objective",
			"objective_title": "Unauthorized Objective",
			"cycle": self.cycle.name,
			"objective_type": "Department",
			"status": "Draft"
		})
		self.assertRaises(frappe.PermissionError, new_objective.insert)

		frappe.set_user("Administrator")
