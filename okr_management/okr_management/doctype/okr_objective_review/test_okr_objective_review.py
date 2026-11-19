from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from okr_management.insights import get_review_rating_rows


class TestOKRObjectiveReview(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        company = frappe.db.get_value("Company", {}, "name")
        fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            {"year_start_date": ["<=", today()], "year_end_date": [">=", today()]},
            "name",
        )
        if not company or not fiscal_year:
            self.skipTest("Required ERP masters are missing.")

        self.plan = frappe.get_doc(
            {
                "doctype": "OKR Plan",
                "plan_name": "Review Test " + frappe.generate_hash(length=8),
                "financial_year": fiscal_year,
                "company": company,
                "owner_user": "Administrator",
                "sprint_frequency": "Monthly",
                "planned_activation_date": today(),
                "status": "Draft",
            }
        ).insert(ignore_permissions=True)
        group = frappe.get_doc(
            {
                "doctype": "Group",
                "group_name": "Review Group " + frappe.generate_hash(length=8),
                "company": company,
            }
        ).insert(ignore_permissions=True)
        self.objective = frappe.get_doc(
            {
                "doctype": "OKR Objective",
                "objective_title": "Review Objective " + frappe.generate_hash(length=8),
                "parent_plan": self.plan.name,
                "group": group.name,
                "owner_user": "Administrator",
                "status": "Draft",
            }
        ).insert(ignore_permissions=True)
        self.review = frappe.get_doc(
            {
                "doctype": "OKR Objective Review",
                "objective": self.objective.name,
                "reviewer": "Administrator",
                "review_date": today(),
                "manager_rating": 0.8,
                "review_status": "Draft",
            }
        ).insert(ignore_permissions=True)

    def test_review_loads_without_removed_sprint_field(self):
        review = frappe.get_doc("OKR Objective Review", self.review.name)

        self.assertEqual(review.objective, self.objective.name)
        self.assertFalse(review.meta.has_field("sprint"))

    def test_review_form_script_does_not_reference_removed_sprint_field(self):
        script_path = frappe.get_app_path(
            "okr_management",
            "okr_management",
            "doctype",
            "okr_objective_review",
            "okr_objective_review.js",
        )
        with open(script_path, encoding="utf-8") as script_file:
            script = script_file.read()

        self.assertNotIn("sprint", script.lower())

    def test_review_rating_rows_derive_plan_from_objective(self):
        rows = get_review_rating_rows(include_normal=True)
        row = next(item for item in rows if item["review"] == self.review.name)

        self.assertEqual(row["plan"], self.plan.name)
        self.assertNotIn("sprint", row)
