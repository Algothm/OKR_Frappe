from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from okr_management import insights


class TestExecutiveReportEscaping(FrappeTestCase):
    def test_untrusted_report_values_are_html_escaped(self):
        payload = '<img src=x onerror="window.__okr_xss=1">'
        escaped = "&lt;img src=x onerror=&#34;window.__okr_xss=1&#34;&gt;"
        context = {
            "generated_on_display": "2026-11-19",
            "company": payload,
            "active_plan_name": payload,
            "summary": {"average_company_progress": 0, "objectives_at_risk": 1},
            "summary_cards": [],
            "total_objectives": 1,
            "active_objectives": 1,
            "completed_objectives": 0,
            "top_department": {"department": payload, "average_progress": 0, "at_risk": 0},
            "lowest_department": {"department": payload, "average_progress": 0, "at_risk": 0},
            "department_performance": [
                {"department": payload, "average_progress": 0, "objective_count": 1, "at_risk": 0}
            ],
            "critical_objectives": ["OBJ-1"],
            "at_risk_objectives": [
                {
                    "title": payload,
                    "record": payload,
                    "owner": payload,
                    "department": payload,
                    "progress": 0,
                    "confidence": 0,
                    "risk_level": "High",
                    "days_remaining_display": "3 days",
                    "end_date_display": "2026-11-22",
                    "reason": payload,
                }
            ],
            "low_confidence_key_results": [],
            "missed_checkins": [],
            "upcoming_deadlines": [],
            "recommended_actions": [payload],
            "review_ratings": {
                "avg_employee_rating": 0,
                "avg_manager_rating": 0,
                "rating_difference": 0,
                "avg_overall_rating": 0,
                "rating_gap_summary": "",
                "total_reviews": 1,
                "low_rating_count": 0,
                "rating_gap_count": 0,
                "distribution": [],
                "distribution_percentages": {},
                "recent_reviews": [
                    {
                        "objective_title": payload,
                        "objective": payload,
                        "reviewer": payload,
                        "self_rating_display": "1.0",
                        "manager_rating_display": "2.0",
                        "overall_rating_display": "1.5",
                        "rating_gap": 0,
                        "review_status": payload,
                    }
                ],
            },
        }

        html = frappe.render_template(insights.EXECUTIVE_REPORT_TEMPLATE, context)

        self.assertNotIn(payload, html)
        self.assertIn(escaped, html)
