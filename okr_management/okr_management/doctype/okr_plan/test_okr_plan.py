import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate


class TestOKRPlanPhase1(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.db.get_value("Company", {}, "name")
        if not self.company:
            self.skipTest("No Company exists on this site.")
        self.fiscal_year = self.ensure_fiscal_year()
        frappe.db.delete("OKR Objective")
        frappe.db.delete("OKR Plan")

    def tearDown(self):
        frappe.set_user("Administrator")

    def ensure_fiscal_year(self):
        current_date = frappe.utils.getdate(frappe.utils.today())
        existing_fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            {
                "year_start_date": ["<=", current_date],
                "year_end_date": [">=", current_date],
            },
            "name",
        )
        if existing_fiscal_year:
            return existing_fiscal_year
        return frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": "FY-" + str(current_date.year),
            "year_start_date": f"{current_date.year}-01-01",
            "year_end_date": f"{current_date.year}-12-31",
        }).insert(ignore_permissions=True).name

    def make_plan(self, status="Draft", **overrides):
        doc = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": overrides.pop("plan_name", "Phase 1 OKR Plan"),
            "financial_year": overrides.pop("financial_year", self.fiscal_year),
            "company": overrides.pop("company", self.company),
            "owner_user": overrides.pop("owner_user", "Administrator"),
            "status": "Draft",
            **overrides,
        })
        doc.insert(ignore_permissions=True)
        if status != "Draft":
            doc.status = status
            doc.save(ignore_permissions=True)
        return doc

    def make_objective(self, plan):
        department = frappe.db.get_value("Department", {"company": self.company}, "name")
        if not department:
            self.skipTest("No Department exists for the test Company.")
        return frappe.get_doc({
            "doctype": "OKR Objective",
            "objective_title": "Phase 1 Dependent Objective",
            "parent_plan": plan.name,
            "department": department,
            "priority": "High",
            "owner_user": "Administrator",
            "status": "Draft",
        }).insert(ignore_permissions=True)

    def test_new_plan_can_start_active(self):
        doc = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": "Can Start Active",
            "financial_year": self.fiscal_year,
            "company": self.company,
            "owner_user": "Administrator",
            "status": "Active",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "Active")

    def test_valid_lifecycle_and_invalid_transition_blocked(self):
        plan = self.make_plan()
        plan.status = "Completed"
        self.assertRaises(frappe.ValidationError, plan.save)

    def test_monthly_sprint_configuration_accepts_month(self):
        plan = self.make_plan(sprint_frequency="Monthly", period_selection="January")
        self.assertEqual(plan.period_selection, "January")

    def test_quarterly_sprint_configuration_rejects_invalid_period(self):
        self.assertRaises(
            frappe.ValidationError,
            self.make_plan,
            sprint_frequency="Quarterly",
            period_selection="January",
        )

    def test_custom_sprint_configuration_accepts_dates_inside_financial_year(self):
        fiscal_year = frappe.db.get_value(
            "Fiscal Year",
            self.fiscal_year,
            ["year_start_date", "year_end_date"],
            as_dict=True,
        )
        plan = self.make_plan(
            sprint_frequency="Custom",
            period_selection="",
            custom_start_date=fiscal_year.year_start_date,
            custom_end_date=add_days(fiscal_year.year_start_date, 10),
        )
        self.assertEqual(plan.sprint_frequency, "Custom")
        plan.reload()

        plan.status = "Active"
        plan.save(ignore_permissions=True)
        plan.status = "Draft"
        plan.save(ignore_permissions=True)
        plan.status = "Archived"
        plan.save(ignore_permissions=True)
        plan.status = "Active"
        plan.save(ignore_permissions=True)

        plan.status = "Closed"
        self.assertRaises(frappe.ValidationError, plan.save)

    def test_active_plan_locks_approved_fields_only(self):
        plan = self.make_plan(status="Active")
        plan.plan_name = "Renamed While Active"
        plan.save(ignore_permissions=True)
        plan.company = "Locked Company Change"
        self.assertRaises(frappe.ValidationError, plan.save)
        plan.reload()
        plan.owner_user = "locked.owner@example.com"
        self.assertRaises(frappe.ValidationError, plan.save)

    def test_progress_is_system_calculated(self):
        plan = self.make_plan(progress=75)
        plan.reload()
        self.assertEqual(plan.progress, 0)
        plan.progress = 95
        plan.save(ignore_permissions=True)
        plan.reload()
        self.assertEqual(plan.progress, 0)

    def test_active_plan_can_be_archived_with_existing_objective(self):
        plan = self.make_plan(status="Active")
        self.make_objective(plan)
        plan.status = "Archived"
        plan.save(ignore_permissions=True)
        plan.reload()
        self.assertEqual(plan.status, "Archived")

    def test_delete_blocked_when_dependent_objective_exists(self):
        plan = self.make_plan(status="Active")
        self.make_objective(plan)
        self.assertRaises(frappe.ValidationError, plan.delete)

    def test_plan_team_automatic_owner_population(self):
        plan = self.make_plan()
        self.assertTrue(len(plan.members) > 0)
        self.assertEqual(plan.members[0].member_user, "Administrator")
        self.assertEqual(plan.members[0].role, "Admin")

    def test_plan_team_multiple_members(self):
        for email in ("test_user1@example.com", "test_user2@example.com"):
            if not frappe.db.exists("User", email):
                frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": "Test",
                    "send_welcome_email": 0
                }).insert(ignore_permissions=True)

        plan = self.make_plan()
        plan.append("members", {
            "member_user": "test_user1@example.com",
            "role": "Admin"
        })
        plan.append("members", {
            "member_user": "test_user2@example.com",
            "role": "Admin"
        })
        plan.save(ignore_permissions=True)
        plan.reload()
        self.assertEqual(len(plan.members), 3)

    def test_plan_team_admin_role_is_valid(self):
        plan = self.make_plan()
        plan.members[0].role = "Admin"
        plan.save(ignore_permissions=True)
        plan.reload()
        self.assertEqual(plan.members[0].role, "Admin")


    def test_plan_team_duplicate_member_blocked(self):
        plan = self.make_plan()
        plan.append("members", {
            "member_user": "Administrator",
            "role": "Admin"
        })
        self.assertRaises(frappe.ValidationError, plan.save)
