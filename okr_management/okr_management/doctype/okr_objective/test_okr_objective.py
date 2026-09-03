from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate


class TestOKRObjectivePlanContext(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.department = frappe.db.get_value("Department", {"company": self.company}, "name")
		if not self.company or not self.department:
			self.skipTest("A Company and Department are required.")
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
		self.assertEqual(getdate(objective.end_date), getdate(fiscal_year.year_end_date))

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
