import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from frappe.utils import getdate
from okr_management.okr_management.doctype.okr_plan.okr_plan import (
    get_derived_periods,
    get_period_label,
    get_default_objective_dates,
    get_plan_context,
)


class TestOKRPlanPhase1(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.db.get_value("Company", {}, "name")
        if not self.company:
            self.skipTest("No Company exists on this site.")
        self.fiscal_year = self.ensure_fiscal_year()
        if not frappe.db.exists("Fiscal Year", "2026-2027"):
            frappe.get_doc({
                "doctype": "Fiscal Year",
                "year": "2026-2027",
                "year_start_date": "2026-04-01",
                "year_end_date": "2027-03-31",
                "companies": [{"company": self.company}],
            }).insert(ignore_permissions=True)
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
            "year_start_date": f"{current_date.year}-04-01",
            "year_end_date": f"{current_date.year + 1}-03-31",
        }).insert(ignore_permissions=True).name

    def make_plan(self, status="Draft", **overrides):
        doc = frappe.get_doc({
            "doctype": "OKR Plan",
            "plan_name": overrides.pop("plan_name", "Phase 1 OKR Plan"),
            "financial_year": overrides.pop("financial_year", self.fiscal_year),
            "company": overrides.pop("company", self.company),
            "owner_user": overrides.pop("owner_user", "Administrator"),
            "status": "Draft",
            "planned_activation_date": overrides.pop("planned_activation_date", nowdate()),
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

    def test_draft_plan_requires_planned_activation_date(self):
        self.assertRaises(
            frappe.ValidationError,
            self.make_plan,
            planned_activation_date=None,
        )

    def test_activation_date_must_be_inside_financial_year(self):
        fiscal = frappe.db.get_value(
            "Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
        )
        self.assertRaises(
            frappe.ValidationError,
            self.make_plan,
            planned_activation_date=add_days(fiscal.year_start_date, -1),
        )
        self.assertRaises(
            frappe.ValidationError,
            self.make_plan,
            planned_activation_date=add_days(fiscal.year_end_date, 1),
        )

    def test_due_draft_plan_and_objective_activate_idempotently(self):
        from okr_management.tasks import activate_due_plans

        plan = self.make_plan(planned_activation_date=nowdate())
        objective = self.make_objective(plan)
        key_result = frappe.get_doc({
            "doctype": "OKR Key Result",
            "key_result_title": "Scheduled Draft KR",
            "objective": objective.name,
            "assignee": "Administrator",
            "owner_user": "Administrator",
            "priority": "High",
            "status": "Draft",
            "calculation_mode": "Manual",
            "metric_type": "Percentage",
            "metric_direction": "Increase",
            "target_value": 100,
            "end_date": objective.end_date,
        }).insert(ignore_permissions=True)
        self.assertIn(plan.name, activate_due_plans(nowdate()))
        plan.reload()
        objective.reload()
        key_result.reload()
        self.assertEqual(plan.status, "Active")
        self.assertEqual(objective.status, "Active")
        self.assertEqual(key_result.status, "Active")
        self.assertNotIn(plan.name, activate_due_plans(nowdate()))

    def test_draft_plan_disables_checkins_server_side(self):
        from okr_management.okr_management.doctype.okr_check_in.okr_check_in import OKRCheckIn

        plan = self.make_plan(planned_activation_date=add_days(nowdate(), 1))
        action = frappe._dict(parent_plan=plan.name, parent_key_result=None)
        checkin = frappe.new_doc("OKR Check In")
        self.assertRaises(frappe.ValidationError, checkin.validate_parent_plan_active, action)

    def test_workspace_plan_source_includes_assigned_drafts(self):
        from okr_management.okr_management.page.okr_workspace.okr_workspace import get_workspace_plan_names

        plan = self.make_plan(planned_activation_date=add_days(nowdate(), 1))
        self.assertIn(plan.name, get_workspace_plan_names())

    def test_future_draft_plan_is_not_activated(self):
        from okr_management.tasks import activate_due_plans

        plan = self.make_plan(planned_activation_date=add_days(nowdate(), 1))
        self.assertNotIn(plan.name, activate_due_plans(nowdate()))
        plan.reload()
        self.assertEqual(plan.status, "Draft")

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

    def test_monthly_derives_fiscal_months(self):
        from okr_management.okr_management.doctype.okr_plan.okr_plan import get_derived_periods, get_plan_timeline
        plan = self.make_plan(sprint_frequency="Monthly")
        fiscal = frappe.db.get_value("Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
        self.assertEqual(get_plan_timeline(plan), (frappe.utils.getdate(fiscal.year_start_date), frappe.utils.getdate(fiscal.year_end_date)))
        self.assertEqual(len(get_derived_periods(plan)), 12)

    def test_quarterly_derives_four_fiscal_quarters(self):
        from okr_management.okr_management.doctype.okr_plan.okr_plan import get_derived_periods
        plan = self.make_plan(sprint_frequency="Quarterly")
        periods = get_derived_periods(plan)
        self.assertEqual([row["label"] for row in periods], ["Q1", "Q2", "Q3", "Q4"])
        self.assertEqual(len(periods), 4)

    def test_custom_frequency_is_rejected(self):
        self.assertRaises(frappe.ValidationError, self.make_plan, sprint_frequency="Custom")

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
        self.assertEqual(plan.members[0].role, "Plan Coordinator")

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
            "role": "Plan Coordinator"
        })
        plan.append("members", {
            "member_user": "test_user2@example.com",
            "role": "Plan Coordinator"
        })
        plan.save(ignore_permissions=True)
        plan.reload()
        self.assertEqual(len(plan.members), 3)

    def test_plan_team_admin_role_is_valid(self):
        plan = self.make_plan()
        plan.members[0].role = "Plan Coordinator"
        plan.save(ignore_permissions=True)
        plan.reload()
        self.assertEqual(plan.members[0].role, "Plan Coordinator")


    def test_period_label_is_derived_from_full_fiscal_year(self):
        plan = self.make_plan(sprint_frequency="Monthly")
        monthly = get_derived_periods(plan)
        self.assertEqual(get_period_label(monthly[0]["start_date"], plan), monthly[0]["label"])
        self.assertEqual(get_period_label(monthly[-1]["end_date"], plan), monthly[-1]["label"])
        self.assertEqual(get_period_label(None, plan), "")
        self.assertEqual(get_period_label(add_days(monthly[0]["start_date"], -1), plan), "")

    def test_period_label_recalculates_when_frequency_changes(self):
        plan = self.make_plan(sprint_frequency="Monthly")
        item_date = get_derived_periods(plan)[1]["start_date"]
        monthly_label = get_period_label(item_date, plan)
        plan.sprint_frequency = "Quarterly"
        self.assertNotEqual(get_period_label(item_date, plan), monthly_label)
        self.assertEqual(get_period_label(item_date, plan), "Q1")

    def test_workspace_payload_labels_key_results_and_actions(self):
        from okr_management.okr_management.page.okr_workspace.okr_workspace import add_period_labels

        plan = self.make_plan(sprint_frequency="Quarterly")
        period = get_derived_periods(plan)[1]
        key_result = frappe._dict(parent_plan=plan.name, end_date=period["start_date"])
        action_item = frappe._dict(parent_plan=plan.name, due_date=period["end_date"])
        unscheduled = frappe._dict(parent_plan=plan.name, due_date=None)

        add_period_labels([key_result], [action_item, unscheduled])
        self.assertEqual(key_result.period_label, "Q2")
        self.assertEqual(action_item.period_label, "Q2")
        self.assertEqual(unscheduled.period_label, "")

    def test_plan_team_duplicate_member_blocked(self):
        plan = self.make_plan()
        plan.append("members", {
            "member_user": "Administrator",
            "role": "Plan Coordinator"
        })
        self.assertRaises(frappe.ValidationError, plan.save)

    def test_default_objective_dates_quarterly_standard_fy(self):
        """
        Requirements A, B, C:
        A. Quarterly 2026-09-04 -> 2026-09-04 to 2026-09-30 (Q2)
        B. Quarterly Q1 2026-05-15 -> 2026-05-15 to 2026-06-30 (Q1)
        C. Quarterly Jan-Mar rollover 2027-02-15 -> 2027-02-15 to 2027-03-31 (Q4)
        """
        plan = self.make_plan(
            financial_year="2026-2027",
            sprint_frequency="Quarterly",
            planned_activation_date="2026-09-04",
        )
        start, end = get_default_objective_dates(plan)
        self.assertEqual(start, getdate("2026-09-04"))
        self.assertEqual(end, getdate("2026-09-30"))

        start, end = get_default_objective_dates(plan, activation_date="2026-04-01")
        self.assertEqual(start, getdate("2026-04-01"))
        self.assertEqual(end, getdate("2026-06-30"))

        start, end = get_default_objective_dates(plan, activation_date="2026-05-15")
        self.assertEqual(start, getdate("2026-05-15"))
        self.assertEqual(end, getdate("2026-06-30"))

        start, end = get_default_objective_dates(plan, activation_date="2026-06-30")
        self.assertEqual(start, getdate("2026-06-30"))
        self.assertEqual(end, getdate("2026-06-30"))

        start, end = get_default_objective_dates(plan, activation_date="2026-07-01")
        self.assertEqual(start, getdate("2026-07-01"))
        self.assertEqual(end, getdate("2026-09-30"))

        start, end = get_default_objective_dates(plan, activation_date="2027-01-10")
        self.assertEqual(start, getdate("2027-01-10"))
        self.assertEqual(end, getdate("2027-03-31"))

        start, end = get_default_objective_dates(plan, activation_date="2027-02-15")
        self.assertEqual(start, getdate("2027-02-15"))
        self.assertEqual(end, getdate("2027-03-31"))

    def test_default_objective_dates_monthly(self):
        """
        Requirements D, E:
        D. Monthly 2026-09-04 -> 2026-09-04 to 2026-09-30
        E. Monthly February non-leap: 2027-02-15 -> 2027-02-15 to 2027-02-28
        """
        plan = self.make_plan(
            financial_year="2026-2027",
            sprint_frequency="Monthly",
            planned_activation_date="2026-09-04",
        )
        start, end = get_default_objective_dates(plan)
        self.assertEqual(start, getdate("2026-09-04"))
        self.assertEqual(end, getdate("2026-09-30"))

        start, end = get_default_objective_dates(plan, activation_date="2027-02-15")
        self.assertEqual(start, getdate("2027-02-15"))
        self.assertEqual(end, getdate("2027-02-28"))

    def test_default_objective_dates_non_april_and_leap_year(self):
        """
        Requirement F and leap year February:
        Non-April FY: Calendar year 2028 (2028-01-01 to 2028-12-31)
        """
        fy_name = "_Test Fiscal Year 2028"
        if not frappe.db.exists("Fiscal Year", fy_name):
            self.skipTest(f"{fy_name} does not exist")

        plan_monthly = {
            "financial_year": fy_name,
            "sprint_frequency": "Monthly",
            "planned_activation_date": "2028-02-15",
        }
        start, end = get_default_objective_dates(plan_monthly)
        self.assertEqual(start, getdate("2028-02-15"))
        self.assertEqual(end, getdate("2028-02-29"))

        plan_quarterly = {
            "financial_year": fy_name,
            "sprint_frequency": "Quarterly",
            "planned_activation_date": "2028-05-10",
        }
        start, end = get_default_objective_dates(plan_quarterly)
        self.assertEqual(start, getdate("2028-05-10"))
        self.assertEqual(end, getdate("2028-06-30"))

        start, end = get_default_objective_dates(plan_quarterly, activation_date="2028-01-15")
        self.assertEqual(start, getdate("2028-01-15"))
        self.assertEqual(end, getdate("2028-03-31"))

        start, end = get_default_objective_dates(plan_quarterly, activation_date="2028-11-20")
        self.assertEqual(start, getdate("2028-11-20"))
        self.assertEqual(end, getdate("2028-12-31"))

    def test_plan_context_api_includes_default_objective_dates(self):
        plan = self.make_plan(
            financial_year="2026-2027",
            sprint_frequency="Quarterly",
            planned_activation_date="2026-09-04",
            status="Active",
        )
        context = get_plan_context(plan.name)
        self.assertEqual(context.get("default_start_date"), getdate("2026-09-04"))
        self.assertEqual(context.get("default_end_date"), getdate("2026-09-30"))
        self.assertEqual(context.get("planned_activation_date"), getdate("2026-09-04"))

    def test_period_label_supports_multi_quarter_ranges(self):
        plan = self.make_plan(
            financial_year="2026-2027",
            sprint_frequency="Quarterly",
            planned_activation_date="2026-04-01",
        )
        # 1. Q1: 01-04-2026 -> 30-06-2026
        self.assertEqual(get_period_label("2026-04-01", plan, end_date="2026-06-30"), "Q1")

        # 2. Q2: 01-07-2026 -> 30-09-2026
        self.assertEqual(get_period_label("2026-07-01", plan, end_date="2026-09-30"), "Q2")

        # 3. Q1–Q2: 01-04-2026 -> 30-09-2026
        self.assertEqual(get_period_label("2026-04-01", plan, end_date="2026-09-30"), "Q1–Q2")

        # 4. Q2–Q3: 15-07-2026 -> 31-12-2026
        self.assertEqual(get_period_label("2026-07-15", plan, end_date="2026-12-31"), "Q2–Q3")

        # 5. Q3–Q4: 01-10-2026 -> 31-03-2027
        self.assertEqual(get_period_label("2026-10-01", plan, end_date="2027-03-31"), "Q3–Q4")

        # 6. Q1–Q4: 01-04-2026 -> 31-03-2027
        self.assertEqual(get_period_label("2026-04-01", plan, end_date="2027-03-31"), "Q1–Q4")

        # Non-April FY (CY-2028: 2028-01-01 to 2028-12-31)
        fy_name = "_Test Fiscal Year 2028"
        if frappe.db.exists("Fiscal Year", fy_name):
            plan_cy = {"financial_year": fy_name, "sprint_frequency": "Monthly"}
            self.assertEqual(get_period_label("2028-01-01", plan_cy, end_date="2028-06-30"), "Q1–Q2")
            self.assertEqual(get_period_label("2028-04-15", plan_cy, end_date="2028-09-30"), "Q2–Q3")
            self.assertEqual(get_period_label("2028-01-01", plan_cy, end_date="2028-12-31"), "Q1–Q4")
