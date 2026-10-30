from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_last_day, getdate


class TestOKRObjectivePlanContext(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
		if not self.company or not self.department:
			self.skipTest("A Company and Department are required.")
		self.group = frappe.get_doc({"doctype": "Group", "group_name": "Objective Test " + frappe.generate_hash(length=8), "company": self.company}).insert(ignore_permissions=True).name
		self.fiscal_year = self.ensure_fiscal_year()

	def ensure_fiscal_year(self):
		current = getdate()
		name = frappe.db.get_value(
			"Fiscal Year",
			{"year_start_date": ["<=", current], "year_end_date": [">=", current]},
			"name",
		)
		if name:
			return name
		return (
			frappe.get_doc(
				{
					"doctype": "Fiscal Year",
					"year": f"Objective Plan FY {current.year}",
					"year_start_date": f"{current.year}-04-01",
					"year_end_date": f"{current.year + 1}-03-31",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def make_plan(self, status="Draft"):
		fiscal_year = frappe.db.get_value(
			"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
		)
		plan = frappe.get_doc(
			{
				"doctype": "OKR Plan",
				"plan_name": "Objective Plan " + frappe.generate_hash(length=6),
				"financial_year": self.fiscal_year,
				"company": self.company,
				"owner_user": "Administrator",
				"sprint_frequency": "Monthly",
				"planned_activation_date": fiscal_year.year_start_date,
				"status": "Draft",
			}
		).insert(ignore_permissions=True)
		if status == "Active":
			plan.status = "Active"
			plan.save(ignore_permissions=True)
		return plan

	def make_objective(self, plan=None, **values):
		plan = plan or self.make_plan()
		payload = {
			"doctype": "OKR Objective",
			"objective_title": "Objective " + frappe.generate_hash(length=6),
			"parent_plan": plan.name,
			"department": self.department,
			"group": self.group,
			"priority": "High",
			"owner_user": "Administrator",
			"status": "Draft",
		}
		payload.update(values)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def test_inherits_context_and_timeline_from_plan(self):
		plan = self.make_plan()
		fiscal_year = frappe.db.get_value(
			"Fiscal Year", plan.financial_year, ["year_start_date", "year_end_date"], as_dict=True
		)
		objective = self.make_objective(plan)
		self.assertEqual(objective.parent_plan, plan.name)
		self.assertEqual(objective.financial_year, plan.financial_year)
		self.assertEqual(objective.company, plan.company)
		self.assertEqual(objective.plan_owner, plan.owner_user)
		self.assertEqual(getdate(objective.start_date), getdate(fiscal_year.year_start_date))
		self.assertEqual(getdate(objective.end_date), get_last_day(fiscal_year.year_start_date))

	def test_objective_title_accepts_more_than_140_characters_without_clipping(self):
		long_title = "Long Objective Title " + ("measurable business outcome " * 10)
		self.assertGreater(len(long_title), 209)
		objective = self.make_objective(objective_title=long_title)
		objective.reload()
		self.assertEqual(objective.objective_title, long_title)

	def test_manual_dates_preserved_on_save(self):
		plan = self.make_plan()
		custom_start = "2026-05-01"
		custom_end = "2026-08-31"
		objective = self.make_objective(plan, start_date=custom_start, end_date=custom_end)
		self.assertEqual(getdate(objective.start_date), getdate(custom_start))
		self.assertEqual(getdate(objective.end_date), getdate(custom_end))
		objective.objective_title = "Updated Title " + frappe.generate_hash(length=4)
		objective.save(ignore_permissions=True)
		objective.reload()
		self.assertEqual(getdate(objective.start_date), getdate(custom_start))
		self.assertEqual(getdate(objective.end_date), getdate(custom_end))

	def test_manual_dates_can_span_multiple_quarters(self):
		# Example A: Quarterly activation 01-04-2026 (Q1 default 01-04-2026 -> 30-06-2026)
		# User manually extends end_date to 30-09-2026 (spans Q1 + Q2)
		plan_a = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Quarterly Plan A " + frappe.generate_hash(length=6),
			"financial_year": self.fiscal_year,
			"company": self.company,
			"owner_user": "Administrator",
			"sprint_frequency": "Quarterly",
			"planned_activation_date": "2026-04-01",
			"status": "Draft",
		}).insert(ignore_permissions=True)

		obj_a = self.make_objective(plan_a, start_date="2026-04-01", end_date="2026-09-30")
		self.assertEqual(getdate(obj_a.start_date), getdate("2026-04-01"))
		self.assertEqual(getdate(obj_a.end_date), getdate("2026-09-30"))

		# Example B: Quarterly activation 01-07-2026 (Q2 default 01-07-2026 -> 30-09-2026)
		# User manually extends end_date to 31-12-2026 (spans Q2 + Q3)
		plan_b = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Quarterly Plan B " + frappe.generate_hash(length=6),
			"financial_year": self.fiscal_year,
			"company": self.company,
			"owner_user": "Administrator",
			"sprint_frequency": "Quarterly",
			"planned_activation_date": "2026-07-01",
			"status": "Draft",
		}).insert(ignore_permissions=True)

		obj_b = self.make_objective(plan_b, start_date="2026-07-01", end_date="2026-12-31")
		self.assertEqual(getdate(obj_b.start_date), getdate("2026-07-01"))
		self.assertEqual(getdate(obj_b.end_date), getdate("2026-12-31"))

	def test_manual_dates_can_span_multiple_months(self):
		# Example C: Monthly activation 04-09-2026 (Sep default 01-09-2026 -> 30-09-2026)
		# User manually extends end_date to 31-10-2026 (spans Sep + Oct)
		plan_c = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Monthly Plan C " + frappe.generate_hash(length=6),
			"financial_year": self.fiscal_year,
			"company": self.company,
			"owner_user": "Administrator",
			"sprint_frequency": "Monthly",
			"planned_activation_date": "2026-09-04",
			"status": "Draft",
		}).insert(ignore_permissions=True)

		obj_c = self.make_objective(plan_c, start_date="2026-09-01", end_date="2026-10-31")
		self.assertEqual(getdate(obj_c.start_date), getdate("2026-09-01"))
		self.assertEqual(getdate(obj_c.end_date), getdate("2026-10-31"))

	def test_manual_dates_outside_plan_timeline_rejected(self):
		# Example D: Manual date outside Plan timeline is rejected
		plan = self.make_plan()
		fiscal = frappe.db.get_value(
			"Fiscal Year", plan.financial_year, ["year_start_date", "year_end_date"], as_dict=True
		)
		self.assertRaises(
			frappe.ValidationError,
			self.make_objective,
			plan,
			start_date=add_days(fiscal.year_start_date, -1),
			end_date="2026-09-30",
		)
		self.assertRaises(
			frappe.ValidationError,
			self.make_objective,
			plan,
			start_date="2026-04-01",
			end_date=add_days(fiscal.year_end_date, 1),
		)

	def test_default_dates_from_draft_and_active_plan(self):
		draft_plan = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Draft Plan " + frappe.generate_hash(length=6),
			"financial_year": self.fiscal_year,
			"company": self.company,
			"owner_user": "Administrator",
			"sprint_frequency": "Quarterly",
			"planned_activation_date": "2026-09-04",
			"status": "Draft",
		}).insert(ignore_permissions=True)
		obj_draft = self.make_objective(draft_plan)
		self.assertEqual(getdate(obj_draft.start_date), getdate("2026-09-04"))
		self.assertEqual(getdate(obj_draft.end_date), getdate("2026-09-30"))

		active_plan = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": "Active Plan " + frappe.generate_hash(length=6),
			"financial_year": self.fiscal_year,
			"company": self.company,
			"owner_user": "Administrator",
			"sprint_frequency": "Quarterly",
			"planned_activation_date": "2026-09-04",
			"status": "Active",
		}).insert(ignore_permissions=True)
		obj_active = self.make_objective(active_plan)
		self.assertEqual(getdate(obj_active.start_date), getdate("2026-09-04"))
		self.assertEqual(getdate(obj_active.end_date), getdate("2026-09-30"))

	def test_dates_must_stay_inside_plan_period(self):
		plan = self.make_plan()
		self.assertRaises(
			frappe.ValidationError,
			self.make_objective,
			plan,
			start_date=add_days(
				frappe.db.get_value("Fiscal Year", plan.financial_year, "year_start_date"), -1
			),
			end_date=frappe.db.get_value("Fiscal Year", plan.financial_year, "year_end_date"),
		)

	def test_duplicate_title_is_scoped_to_plan(self):
		plan = self.make_plan()
		title = "Unique Plan Objective " + frappe.generate_hash(length=6)
		self.make_objective(plan, objective_title=title)
		self.assertRaises(frappe.ValidationError, self.make_objective, plan, objective_title=title)

	def test_active_objective_requires_active_plan(self):
		draft_plan = self.make_plan()
		objective = self.make_objective(draft_plan)
		objective.status = "Active"
		self.assertRaises(frappe.ValidationError, objective.save)

		active_plan = self.make_plan(status="Active")
		active_objective = self.make_objective(active_plan)
		active_objective.status = "Active"
		active_objective.save(ignore_permissions=True)
		self.assertEqual(active_objective.status, "Active")

	def test_active_objective_can_close_directly_and_persists_closed_label(self):
		plan = self.make_plan(status="Active")
		objective = self.make_objective(plan, status="Active")
		objective.status = "Closed"
		objective.save(ignore_permissions=True)
		objective.reload()
		self.assertEqual(objective.status, "Closed")

	def test_objective_scope_is_always_department(self):
		objective = self.make_objective(level="Team")
		self.assertEqual(objective.level, "Department")
		self.assertEqual(frappe.get_meta("OKR Objective").get_field("level").options, "Department")

	def test_department_is_required(self):
		self.assertRaises(frappe.ValidationError, self.make_objective, department=None)

	def test_department_search_returns_existing_departments(self):
		from okr_management.okr_management.doctype.okr_objective.okr_objective import (
			search_plan_departments,
		)

		all_rows = search_plan_departments("Department", "", "name", 0, 100, {})
		self.assertIn(self.department, {row[0] for row in all_rows})

		plan = self.make_plan()
		plan_rows = search_plan_departments("Department", "", "name", 0, 100, {"parent_plan": plan.name})
		self.assertIn(self.department, {row[0] for row in plan_rows})

	def test_objective_post_save_dates_and_fields_editable_and_persist(self):
		plan = self.make_plan(status="Active")
		obj = self.make_objective(plan, start_date="2026-04-01", end_date="2026-06-30", status="Active")
		self.assertEqual(getdate(obj.start_date), getdate("2026-04-01"))
		self.assertEqual(getdate(obj.end_date), getdate("2026-06-30"))

		# First save edit: change End Date and Title
		obj.end_date = "2026-09-30"
		new_title = "Objective Updated Once " + frappe.generate_hash(length=4)
		obj.objective_title = new_title
		obj.save(ignore_permissions=True)
		obj.reload()
		self.assertEqual(getdate(obj.end_date), getdate("2026-09-30"))
		self.assertEqual(obj.objective_title, new_title)

		# Second save edit: change Start Date
		obj.start_date = "2026-04-15"
		obj.save(ignore_permissions=True)
		obj.reload()
		self.assertEqual(getdate(obj.start_date), getdate("2026-04-15"))
		self.assertEqual(getdate(obj.end_date), getdate("2026-09-30"))

	def test_objective_unauthorized_user_write_denied(self):
		plan = self.make_plan(status="Active")
		obj = self.make_objective(plan, owner_user="Administrator")
		test_user = "unauth_user_" + frappe.generate_hash(length=6) + "@example.com"
		if not frappe.db.exists("User", test_user):
			frappe.get_doc({
				"doctype": "User",
				"email": test_user,
				"first_name": "Unauth",
				"roles": [{"role": "All"}],
			}).insert(ignore_permissions=True)

		frappe.set_user(test_user)
		try:
			obj_doc = frappe.get_doc("OKR Objective", obj.name)
			obj_doc.objective_title = "Unauthorized Hack"
			self.assertRaises(frappe.PermissionError, obj_doc.save)
		finally:
			frappe.set_user("Administrator")
