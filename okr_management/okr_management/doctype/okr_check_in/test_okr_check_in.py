import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate, flt, getdate


class TestOKRCheckIn(FrappeTestCase):
	def setUp(self):
		self._original_attach_print = frappe.attach_print
		frappe.attach_print = lambda *args, **kwargs: {"fname": "dummy.pdf", "fcontent": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<Root 1 0 R>>\n%%EOF"}

		# Temporarily deactivate workflows for testing
		self._active_workflows = frappe.get_all("Workflow", filters={"document_type": ["in", ["OKR Plan", "OKR Plan", "OKR Objective", "OKR Key Result"]], "is_active": 1}, fields=["name"])
		for wf in self._active_workflows:
			frappe.db.set_value("Workflow", wf.name, "is_active", 0)
		frappe.clear_cache()

		frappe.db.delete("OKR Check In")
		frappe.db.delete("OKR Key Result")
		frappe.db.delete("OKR Objective")
		frappe.db.delete("OKR Plan")
		frappe.db.delete("OKR Plan")

		self.company = frappe.db.get_value("Company", {}, "name")
		if not self.company:
			self.company = frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Company",
				"abbr": "TC",
				"default_currency": "INR",
				"country": "India"
			}).insert(ignore_permissions=True).name

		# Create test plan
		self.plan = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Test plan",
			"financial_year": "2026-2027",
			"status": "Draft"
		}).insert(ignore_permissions=True)
		self.plan.status = "Active"
		self.plan.flags.ignore_workflow = True
		self.plan.save(ignore_permissions=True)

		# Create test sprint
		self.sprint = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Test sprint",
			"parent_plan": self.plan.name,
			"period_selection": "Q2",
			"sprint_year": 2026,
			"start_date": nowdate(),
			"end_date": add_days(nowdate(), 90),
			"status": "Draft"
		}).insert(ignore_permissions=True)
		self.sprint.status = "Planned"
		self.sprint.flags.ignore_workflow = True
		self.sprint.save(ignore_permissions=True)
		self.sprint.status = "Active"
		self.sprint.flags.ignore_workflow = True
		self.sprint.save(ignore_permissions=True)

		# Create test objective
		self.objective = frappe.get_doc({
			"doctype": "OKR Objective",
			"objective_title": "Test objective",
			"sprint": self.sprint.name,
			"level": "Organization",
			"status": "Draft"
		}).insert(ignore_permissions=True)
		self.objective.status = "Planned"
		self.objective.flags.ignore_workflow = True
		self.objective.save(ignore_permissions=True)
		self.objective.status = "Active"
		self.objective.flags.ignore_workflow = True
		self.objective.save(ignore_permissions=True)

	def make_key_result(self, **overrides):
		status = overrides.pop("status", "Active")
		doc = frappe.get_doc({
			"doctype": "OKR Key Result",
			"key_result_title": overrides.pop("key_result_title", "Test KR " + frappe.generate_hash(length=6)),
			"objective": overrides.pop("objective", self.objective.name),
			"owner_user": overrides.pop("owner_user", "Administrator"),
			"calculation_mode": overrides.pop("calculation_mode", "Check-in Based"),
			"metric_type": overrides.pop("metric_type", "Percentage"),
			"metric_direction": overrides.pop("metric_direction", "Increase"),
			"baseline_value": overrides.pop("baseline_value", 0),
			"current_value": overrides.pop("current_value", 0),
			"target_value": overrides.pop("target_value", 100),
			"status": "Draft",
			"start_date": overrides.pop("start_date", nowdate()),
			"end_date": overrides.pop("end_date", add_days(nowdate(), 30)),
			**overrides,
		})
		doc.flags.ignore_workflow = True
		doc.insert(ignore_permissions=True)
		if status in ("Planned", "Active"):
			doc.status = "Planned"
			doc.flags.ignore_workflow = True
			doc.save(ignore_permissions=True)
		if status == "Active":
			doc.status = "Active"
			doc.flags.ignore_workflow = True
			doc.save(ignore_permissions=True)
		return doc

	def test_context_inheritance(self):
		kr = self.make_key_result()
		checkin = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 20.0,
			"confidence": "Green",
			"status": "Draft"
		})
		checkin.insert(ignore_permissions=True)
		self.assertEqual(checkin.objective, kr.objective)
		self.assertEqual(checkin.parent_plan, kr.parent_plan)
		self.assertEqual(checkin.parent_plan, kr.parent_plan)
		self.assertEqual(checkin.financial_year, kr.financial_year)
		self.assertEqual(checkin.company, kr.company)
		self.assertEqual(checkin.department, kr.department)

	def test_parent_active_status_dependency(self):
		# Create key results with inactive statuses
		for status in ["Draft", "Planned", "On Hold", "Completed", "Closed", "Archived"]:
			kr = self.make_key_result(status=status)
			checkin = frappe.get_doc({
				"doctype": "OKR Check In",
				"key_result": kr.name,
				"current_value": 10.0,
				"confidence": "Yellow",
				"status": "Draft"
			})
			self.assertRaises(frappe.ValidationError, checkin.insert)

	def test_parent_hierarchy_integrity(self):
		# Key Result missing objective / sprint / plan should be blocked
		kr = self.make_key_result()
		# Clear sprint and plan on Key Result (bypassing validations)
		frappe.db.set_value("OKR Key Result", kr.name, {"parent_plan": None, "parent_plan": None})
		checkin = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 10.0,
			"confidence": "Yellow",
			"status": "Draft"
		})
		self.assertRaises(frappe.ValidationError, checkin.insert)

	def test_date_range_validations(self):
		kr = self.make_key_result(start_date=nowdate(), end_date=add_days(nowdate(), 10))
		
		# Date before start_date should fail
		checkin_early = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": add_days(nowdate(), -1),
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Draft"
		})
		self.assertRaises(frappe.ValidationError, checkin_early.insert)

		# Date after end_date should fail
		checkin_late = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": add_days(nowdate(), 11),
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Draft"
		})
		self.assertRaises(frappe.ValidationError, checkin_late.insert)

	def test_future_checkin_date_validation(self):
		kr = self.make_key_result(start_date=nowdate(), end_date=add_days(nowdate(), 15))
		
		# Future date for Draft should pass
		checkin_draft = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": add_days(nowdate(), 5),
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Draft"
		})
		checkin_draft.insert(ignore_permissions=True) # Should succeed

		# Future date for Submitted should fail
		checkin_sub = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": add_days(nowdate(), 5),
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Submitted"
		})
		self.assertRaises(frappe.ValidationError, checkin_sub.insert)

	def test_progress_calculation(self):
		# Increase metric direction
		kr_inc = self.make_key_result(baseline_value=10, target_value=50, metric_direction="Increase")
		checkin_inc = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr_inc.name,
			"current_value": 30.0,
			"confidence": "Green",
			"status": "Draft"
		}).insert(ignore_permissions=True)
		self.assertEqual(checkin_inc.progress, 50.0)

		# Decrease metric direction
		kr_dec = self.make_key_result(baseline_value=100, target_value=20, metric_direction="Decrease")
		checkin_dec = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr_dec.name,
			"current_value": 60.0,
			"confidence": "Green",
			"status": "Draft"
		}).insert(ignore_permissions=True)
		# (100 - 60) / (100 - 20) * 100 = 50%
		self.assertEqual(checkin_dec.progress, 50.0)

	def test_duplicate_submitted_checkin_per_day(self):
		kr = self.make_key_result()
		checkin1 = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": nowdate(),
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Submitted"
		}).insert(ignore_permissions=True)

		# Second submitted checkin on the same day should fail
		checkin2 = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": nowdate(),
			"current_value": 15.0,
			"confidence": "Green",
			"status": "Submitted"
		})
		self.assertRaises(frappe.ValidationError, checkin2.insert)

	def test_historical_checkin_date_validation(self):
		kr = self.make_key_result(start_date=add_days(nowdate(), -4))
		checkin1 = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": add_days(nowdate(), -2),
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Submitted"
		}).insert(ignore_permissions=True)

		# Checkin date earlier than checkin1 date should fail
		checkin2 = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"checkin_date": add_days(nowdate(), -3),
			"current_value": 15.0,
			"confidence": "Green",
			"status": "Draft"
		})
		self.assertRaises(frappe.ValidationError, checkin2.insert)

	def test_submitted_read_only_behavior(self):
		kr = self.make_key_result()
		checkin = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Submitted"
		}).insert(ignore_permissions=True)

		checkin.current_value = 20.0
		self.assertRaises(frappe.ValidationError, checkin.save)

	def test_delete_restriction(self):
		kr = self.make_key_result()
		
		# Draft checkin deletion should pass
		checkin_draft = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Draft"
		}).insert(ignore_permissions=True)
		checkin_draft.delete() # Should not raise error

		# Submitted checkin deletion should fail
		checkin_sub = frappe.get_doc({
			"doctype": "OKR Check In",
			"key_result": kr.name,
			"current_value": 10.0,
			"confidence": "Green",
			"status": "Submitted"
		}).insert(ignore_permissions=True)
		self.assertRaises(frappe.ValidationError, checkin_sub.delete)

	def tearDown(self):
		if hasattr(self, "_original_attach_print"):
			frappe.attach_print = self._original_attach_print

		# Restore workflows
		if hasattr(self, "_active_workflows"):
			for wf in self._active_workflows:
				frappe.db.set_value("Workflow", wf.name, "is_active", 1)
			frappe.clear_cache()
