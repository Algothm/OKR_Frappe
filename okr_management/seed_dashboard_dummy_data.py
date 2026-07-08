from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe.utils import flt

from okr_management.utils.okr_calculations import recalculate_key_result_progress


COMPANY = "AJANTA BOTTLE PRIVATE LIMITED"
FISCAL_YEAR = "2026-2027"
DATASET_TAG = "Dashboard Seed FY27"

USERS = [
    "utsav@algothm.com",
    "gauravjain@ajantabottle.com",
    "hr@ajantabottle.com",
    "acc@ajantabottle.com",
    "akashpandey@ajantabottle.com",
    "create@ajantabottle.com",
    "amitkumar@ajantabottle.com",
    "deepak@ajantabottle.com",
]

DEPARTMENTS = {
    "Sales": "Sales - ABPL",
    "HR": "Human Resource - ABPL",
    "Marketing": "Marketing - ABPL",
    "Production": "NPD  - ABPL",
    "Finance": "Accounts - ABPL",
    "Procurement": "Purchase - ABPL",
    "Quality": "R & D - ABPL",
    "Logistics": "Dispatch & Logistics  - ABPL",
}


PLANS = [
    {
        "plan_name": f"{DATASET_TAG} - Commercial Growth",
        "department": DEPARTMENTS["Sales"],
        "owner": USERS[1],
        "description": "Revenue, market expansion, and customer retention OKRs for FY27.",
        "sprints": [
            {
                "name": "Q1 Commercial Execution Sprint",
                "owner": USERS[1],
                "status": "Active",
                "start": date(2026, 4, 1),
                "end": date(2026, 7, 31),
                "objectives": [
                    {
                        "title": "Increase revenue from pharma and FMCG accounts",
                        "department": DEPARTMENTS["Sales"],
                        "owner": USERS[1],
                        "priority": "High",
                        "krs": [
                            {
                                "title": "Grow qualified pharma pipeline to INR 4.5 Cr",
                                "owner": USERS[1],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Map top 60 pharma prospects with packaging demand", USERS[1], "High", "In Progress", 55),
                                    ("Run distributor follow-up cadence for western region", USERS[6], "Medium", "Open", 35),
                                    ("Prepare ROI deck for high-volume conversion accounts", USERS[5], "High", "In Progress", 62),
                                    ("Resolve sample dispatch delays for enterprise trials", USERS[7], "High", "Blocked", 28),
                                ],
                            },
                            {
                                "title": "Improve repeat order rate from key accounts to 72%",
                                "owner": USERS[6],
                                "priority": "Medium",
                                "target": 100,
                                "actions": [
                                    ("Segment top 40 repeat customers by reorder cycle", USERS[6], "Medium", "Completed", 100),
                                    ("Create monthly review tracker for strategic accounts", USERS[1], "Medium", "In Progress", 70),
                                    ("Close service escalations pending with dispatch team", USERS[7], "High", "Blocked", 45),
                                ],
                            },
                        ],
                    },
                    {
                        "title": "Improve brand visibility in priority industrial clusters",
                        "department": DEPARTMENTS["Marketing"],
                        "owner": USERS[5],
                        "priority": "Medium",
                        "krs": [
                            {
                                "title": "Generate 850 qualified campaign leads by July",
                                "owner": USERS[5],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Launch LinkedIn campaign for pharma procurement heads", USERS[5], "High", "In Progress", 48),
                                    ("Publish case study for bottle quality improvements", USERS[5], "Medium", "Completed", 100),
                                    ("Coordinate webinar with sales team for FMCG buyers", USERS[1], "Medium", "Open", 30),
                                    ("Clean campaign source data for dashboard attribution", USERS[4], "Low", "In Progress", 52),
                                ],
                            },
                            {
                                "title": "Raise website enquiry conversion rate to 6%",
                                "owner": USERS[4],
                                "priority": "Medium",
                                "target": 100,
                                "actions": [
                                    ("Improve landing page copy for pharma product pages", USERS[4], "Medium", "In Progress", 60),
                                    ("Add enquiry source tracking to CRM handoff", USERS[4], "High", "Blocked", 32),
                                    ("Review weekly conversion drop-off with sales ops", USERS[1], "Medium", "Open", 40),
                                ],
                            },
                        ],
                    },
                    {
                        "title": "Strengthen sales operations and forecasting discipline",
                        "department": DEPARTMENTS["Sales"],
                        "owner": USERS[6],
                        "priority": "High",
                        "krs": [
                            {
                                "title": "Maintain weekly forecast accuracy above 85%",
                                "owner": USERS[6],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Standardize deal stage definitions across regions", USERS[6], "Medium", "Completed", 100),
                                    ("Review stuck opportunities older than 21 days", USERS[1], "High", "In Progress", 66),
                                    ("Automate forecast variance report for managers", USERS[4], "Medium", "Open", 38),
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "name": "Q2 Commercial Planning Sprint",
                "owner": USERS[1],
                "status": "Planned",
                "start": date(2026, 8, 1),
                "end": date(2026, 9, 30),
                "objectives": [],
            },
        ],
    },
    {
        "plan_name": f"{DATASET_TAG} - Operational Excellence",
        "department": DEPARTMENTS["Production"],
        "owner": USERS[7],
        "description": "Manufacturing reliability, quality, cost control, and people readiness OKRs.",
        "sprints": [
            {
                "name": "Q1 Operations Execution Sprint",
                "owner": USERS[7],
                "status": "Active",
                "start": date(2026, 4, 1),
                "end": date(2026, 7, 31),
                "objectives": [
                    {
                        "title": "Improve production throughput and schedule adherence",
                        "department": DEPARTMENTS["Production"],
                        "owner": USERS[7],
                        "priority": "High",
                        "krs": [
                            {
                                "title": "Reduce average production changeover time by 18%",
                                "owner": USERS[7],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Time-study current changeover process on Line 2", USERS[7], "High", "Completed", 100),
                                    ("Prepare standard changeover checklist by SKU family", USERS[6], "Medium", "In Progress", 58),
                                    ("Train shift supervisors on quick-change practices", USERS[2], "Medium", "Open", 42),
                                    ("Fix tooling availability gaps for night shift", USERS[7], "High", "Blocked", 34),
                                ],
                            },
                            {
                                "title": "Lift daily schedule adherence to 92%",
                                "owner": USERS[7],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Create daily production variance dashboard", USERS[4], "Medium", "In Progress", 64),
                                    ("Align raw material readiness with purchase team", USERS[7], "High", "Blocked", 47),
                                    ("Run morning huddles for bottleneck escalation", USERS[7], "Medium", "In Progress", 75),
                                ],
                            },
                        ],
                    },
                    {
                        "title": "Improve quality consistency and reduce customer complaints",
                        "department": DEPARTMENTS["Quality"],
                        "owner": USERS[4],
                        "priority": "High",
                        "krs": [
                            {
                                "title": "Reduce defect rate in priority SKUs below 1.2%",
                                "owner": USERS[4],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Audit mould temperature variance for top SKUs", USERS[4], "High", "In Progress", 57),
                                    ("Implement first-piece approval checklist", USERS[7], "Medium", "Completed", 100),
                                    ("Calibrate inspection gauges for QA stations", USERS[4], "Medium", "Open", 44),
                                    ("Resolve vendor resin quality inconsistency", USERS[7], "High", "Blocked", 26),
                                ],
                            },
                            {
                                "title": "Close customer complaint CAPA within 7 working days",
                                "owner": USERS[4],
                                "priority": "Medium",
                                "target": 100,
                                "actions": [
                                    ("Categorize open complaints by root cause", USERS[4], "Medium", "Completed", 100),
                                    ("Set weekly CAPA review with production leads", USERS[7], "Medium", "In Progress", 68),
                                    ("Create evidence pack template for customer closure", USERS[5], "Low", "Open", 36),
                                ],
                            },
                        ],
                    },
                    {
                        "title": "Stabilize procurement and finance controls for operations",
                        "department": DEPARTMENTS["Procurement"],
                        "owner": USERS[3],
                        "priority": "Medium",
                        "krs": [
                            {
                                "title": "Improve raw material availability for priority lines to 96%",
                                "owner": USERS[3],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Create supplier risk tracker for resin vendors", USERS[3], "High", "In Progress", 50),
                                    ("Negotiate backup supply for critical material grades", USERS[3], "High", "Blocked", 30),
                                    ("Set reorder alerts for fast-moving raw materials", USERS[4], "Medium", "In Progress", 72),
                                ],
                            },
                            {
                                "title": "Reduce overdue vendor reconciliations by 40%",
                                "owner": USERS[3],
                                "priority": "Medium",
                                "target": 100,
                                "actions": [
                                    ("Reconcile top 20 vendor balances", USERS[3], "Medium", "In Progress", 63),
                                    ("Digitize missing GRN and invoice attachments", USERS[3], "Low", "Open", 41),
                                    ("Resolve price variance approvals over INR 2 lakh", USERS[7], "High", "Blocked", 35),
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "name": "Q2 Operations Planning Sprint",
                "owner": USERS[7],
                "status": "Draft",
                "start": date(2026, 8, 1),
                "end": date(2026, 9, 30),
                "objectives": [],
            },
        ],
    },
    {
        "plan_name": f"{DATASET_TAG} - People and Culture",
        "department": DEPARTMENTS["HR"],
        "owner": USERS[2],
        "description": "Employee capability, hiring velocity, and engagement OKRs.",
        "sprints": [
            {
                "name": "Q1 People Execution Sprint",
                "owner": USERS[2],
                "status": "Active",
                "start": date(2026, 4, 1),
                "end": date(2026, 7, 31),
                "objectives": [
                    {
                        "title": "Improve hiring velocity and onboarding quality",
                        "department": DEPARTMENTS["HR"],
                        "owner": USERS[2],
                        "priority": "High",
                        "krs": [
                            {
                                "title": "Reduce average time-to-fill for critical roles to 28 days",
                                "owner": USERS[2],
                                "priority": "High",
                                "target": 100,
                                "actions": [
                                    ("Build shortlist pipeline for sales and production roles", USERS[2], "High", "In Progress", 54),
                                    ("Standardize interview scorecards across functions", USERS[2], "Medium", "Completed", 100),
                                    ("Close offer approvals pending with finance", USERS[3], "High", "Blocked", 33),
                                ],
                            },
                            {
                                "title": "Raise 30-day onboarding completion to 95%",
                                "owner": USERS[2],
                                "priority": "Medium",
                                "target": 100,
                                "actions": [
                                    ("Create role-based onboarding checklist", USERS[2], "Medium", "Completed", 100),
                                    ("Schedule production safety induction slots weekly", USERS[7], "Medium", "In Progress", 59),
                                    ("Track pending IT access for new joiners", USERS[4], "Medium", "Open", 46),
                                ],
                            },
                        ],
                    },
                    {
                        "title": "Build frontline capability and engagement",
                        "department": DEPARTMENTS["HR"],
                        "owner": USERS[2],
                        "priority": "Medium",
                        "krs": [
                            {
                                "title": "Train 120 frontline employees on quality and safety basics",
                                "owner": USERS[2],
                                "priority": "Medium",
                                "target": 100,
                                "actions": [
                                    ("Finalize training calendar with production supervisors", USERS[2], "Medium", "In Progress", 61),
                                    ("Deliver first batch safety refresher sessions", USERS[7], "High", "Completed", 100),
                                    ("Collect post-training quiz scores and attendance", USERS[2], "Low", "Open", 39),
                                ],
                            }
                        ],
                    },
                ],
            },
            {
                "name": "Q2 People Planning Sprint",
                "owner": USERS[2],
                "status": "Planned",
                "start": date(2026, 8, 1),
                "end": date(2026, 9, 30),
                "objectives": [],
            },
        ],
    },
]


def create_dashboard_dummy_data() -> dict[str, int | str]:
    ensure_master_data()
    frappe.flags.in_install = "frappe"

    if frappe.db.exists("OKR Plan", {"plan_name": PLANS[0]["plan_name"]}):
        return {"status": "skipped", "reason": f"{DATASET_TAG} data already exists"}

    counts = {
        "plans": 0,
        "sprints": 0,
        "objectives": 0,
        "key_results": 0,
        "action_items": 0,
        "check_ins": 0,
    }

    for plan_spec in PLANS:
        plan = create_plan(plan_spec)
        counts["plans"] += 1

        for sprint_spec in plan_spec["sprints"]:
            sprint = create_sprint(plan, sprint_spec)
            counts["sprints"] += 1

            for objective_spec in sprint_spec["objectives"]:
                objective = create_objective(plan, sprint, objective_spec)
                counts["objectives"] += 1

                for kr_spec in objective_spec["krs"]:
                    key_result = create_key_result(objective, kr_spec)
                    counts["key_results"] += 1
                    action_items = []

                    for index, action_spec in enumerate(kr_spec["actions"]):
                        action_item = create_action_item(key_result, action_spec, index)
                        action_items.append(action_item)
                        counts["action_items"] += 1

                    sync_key_result_child_rows(key_result.name, action_items)
                    counts["check_ins"] += create_checkins_for_key_result(key_result, action_items)
                    recalculate_key_result_progress(key_result.name)

    frappe.db.commit()
    counts["status"] = "created"
    counts["dataset"] = DATASET_TAG
    return counts


def ensure_master_data() -> None:
    if not frappe.db.exists("Company", COMPANY):
        frappe.throw(f"Company not found: {COMPANY}")
    if not frappe.db.exists("Fiscal Year", FISCAL_YEAR):
        frappe.throw(f"Fiscal Year not found: {FISCAL_YEAR}")
    for department in sorted(set(DEPARTMENTS.values())):
        if not frappe.db.exists("Department", department):
            frappe.throw(f"Department not found: {department}")


def user(index_or_user: int | str) -> str:
    preferred = USERS[index_or_user] if isinstance(index_or_user, int) else index_or_user
    if frappe.db.exists("User", preferred):
        return preferred
    fallback = frappe.session.user if frappe.db.exists("User", frappe.session.user) else "Administrator"
    return fallback


def create_plan(spec: dict) -> frappe.model.document.Document:
    doc = frappe.get_doc(
        {
            "doctype": "OKR Plan",
            "financial_year": FISCAL_YEAR,
            "plan_name": spec["plan_name"],
            "company": COMPANY,
            "department": spec["department"],
            "owner_user": user(spec["owner"]),
            "status": "Draft",
            "description": spec["description"],
            "members": [
                {"member_user": user(spec["owner"]), "role": "Owner"},
                {"member_user": user(0), "role": "Viewer"},
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.status = "Active"
    doc.save(ignore_permissions=True)
    return doc


def create_sprint(plan, spec: dict) -> frappe.model.document.Document:
    doc = frappe.get_doc(
        {
            "doctype": "OKR Sprint",
            "parent_plan": plan.name,
            "sprint_name": spec["name"],
            "sprint_owner": user(spec["owner"]),
            "description": f"{spec['name']} for {plan.plan_name}",
            "sprint_cycle": "Custom Date Range",
            "start_date": spec["start"],
            "end_date": spec["end"],
            "status": "Draft",
        }
    )
    doc.insert(ignore_permissions=True)
    if spec["status"] in {"Planned", "Active"}:
        doc.status = "Planned"
        doc.save(ignore_permissions=True)
    if spec["status"] == "Active":
        doc.sprint_year = doc.get_db_value("sprint_year")
        doc.status = "Active"
        doc.save(ignore_permissions=True)
    return doc


def create_objective(plan, sprint, spec: dict) -> frappe.model.document.Document:
    doc = frappe.get_doc(
        {
            "doctype": "OKR Objective",
            "objective_title": spec["title"],
            "sprint": sprint.name,
            "level": "Department",
            "priority": spec["priority"],
            "owner_user": user(spec["owner"]),
            "reviewer": user(0),
            "description": f"{spec['title']} - measurable department objective for {DATASET_TAG}.",
            "start_date": sprint.start_date,
            "end_date": sprint.end_date,
            "status": "Draft",
        }
    )
    doc.insert(ignore_permissions=True)
    doc.status = "Active"
    doc.save(ignore_permissions=True)
    return doc


def create_key_result(objective, spec: dict) -> frappe.model.document.Document:
    doc = frappe.get_doc(
        {
            "doctype": "OKR Key Result",
            "key_result_title": spec["title"],
            "objective": objective.name,
            "description": f"{spec['title']} measured through connected action-item progress.",
            "owner_user": user(spec["owner"]),
            "priority": spec["priority"],
            "status": "Active",
            "calculation_mode": "Automatic",
            "metric_type": "Percentage",
            "metric_direction": "Increase",
            "baseline_value": 0,
            "target_value": spec.get("target", 100),
            "current_value": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def create_action_item(key_result, spec: tuple, index: int) -> frappe.model.document.Document:
    title, owner, priority, status, progress = spec
    due_date = date(2026, 7, 5) + timedelta(days=index * 3)
    doc = frappe.get_doc(
        {
            "doctype": "OKR Action Item",
            "action_item_title": title,
            "description": f"{title}. Linked to {key_result.key_result_title}.",
            "owner_user": user(owner),
            "priority": priority,
            "status": status,
            "progress": 0,
            "due_date": due_date,
            "parent_key_result": key_result.name,
            "notes": "Initial action item created for analytics dashboard seed data.",
        }
    )
    doc.insert(ignore_permissions=True)
    doc._seed_final_progress = progress
    doc._seed_final_status = status
    return doc


def sync_key_result_child_rows(key_result_name: str, action_items: list) -> None:
    key_result = frappe.get_doc("OKR Key Result", key_result_name)
    key_result.set("action_items", [])
    for item in action_items:
        key_result.append(
            "action_items",
            {
                "action_item_id": item.name,
                "action_item_title": item.action_item_title,
                "owner_user": item.owner_user,
                "priority": item.priority,
                "status": item._seed_final_status,
                "progress": item._seed_final_progress,
                "due_date": item.due_date,
            },
        )
    key_result.save(ignore_permissions=True)


def create_checkins_for_key_result(key_result, action_items: list) -> int:
    created = 0
    start = date(2026, 4, 4)
    kr_date_offset = 0

    for item_index, item in enumerate(action_items):
        final_progress = flt(item._seed_final_progress)
        first_progress = max(5, round(final_progress * 0.35, 2))
        second_progress = max(first_progress + 5, round(final_progress * 0.72, 2))
        progress_points = [first_progress, min(second_progress, final_progress), final_progress]
        if final_progress >= 100:
            progress_points = [35, 72, 100]
        elif final_progress < 40:
            progress_points = [10, 22, final_progress]

        for point_index, progress in enumerate(progress_points):
            checkin_date = start + timedelta(days=kr_date_offset)
            kr_date_offset += 4
            if checkin_date > date(2026, 7, 7):
                checkin_date = date(2026, 7, 7) - timedelta(days=(len(action_items) * 3 - created) % 20)

            status = item._seed_final_status if point_index == len(progress_points) - 1 else "In Progress"
            create_checkin(key_result, item, checkin_date, progress, status, point_index)
            created += 1

    return created


def create_checkin(key_result, action_item, checkin_date: date, progress: float, status: str, point_index: int) -> None:
    blocker = ""
    dependency = ""
    if status == "Blocked":
        blocker = "Awaiting supplier confirmation and internal approval before the next milestone can move."
        dependency = "Dependency on Purchase, Finance, or Production lead response."
    elif status == "In Progress" and point_index == 1:
        dependency = "Needs timely inputs from Sales Ops and department owner."

    doc = frappe.get_doc(
        {
            "doctype": "OKR Check In",
            "key_result": key_result.name,
            "reported_by": user(action_item.owner_user),
            "checkin_date": checkin_date,
            "progress": progress,
            "current_value": progress,
            "achievements": progress_note(action_item.action_item_title, progress, status),
            "blockers": blocker,
            "dependency_description": dependency,
            "confidence": "Green" if progress >= 70 else "Yellow" if progress >= 35 else "Red",
            "attachment": "",
            "action_items": [
                {
                    "action_item_id": action_item.name,
                    "action_item_title": action_item.action_item_title,
                    "owner_user": action_item.owner_user,
                    "priority": action_item.priority,
                    "status": status,
                    "progress": progress,
                    "due_date": action_item.due_date,
                    "notes": f"Check-in update at {progress}% for dashboard seed data.",
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)


def progress_note(title: str, progress: float, status: str) -> str:
    if status == "Completed":
        return f"Completed {title}; evidence reviewed and outcome accepted by the owner."
    if status == "Blocked":
        return f"Progress reached {progress}% for {title}, but the next step is blocked by an external dependency."
    return f"Completed planned work for {title}; progress moved to {progress}% with next actions identified."
