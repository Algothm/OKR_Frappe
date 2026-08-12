from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, flt, formatdate, nowdate

from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


ACTIVE_ACTION_STATUSES = ("Open", "In Progress", "Blocked")
ACTION_STATUS_MAP = {
    "In Progress": "In Progress",
    "Blocked": "Blocked",
    "Archived": "Cancelled",
}


class OKRCheckIn(Document):
    def before_validate(self) -> None:
        self.reported_by = frappe.session.user
        self.checkin_date = nowdate()
        self.status = "Submitted"
        if self.action_item:
            self.populate_from_action_item()
            self.set_metric_progress()
        else:
            self.progress = min(100.0, max(0.0, flt(self.progress)))
            self.progress_percent = self.progress

    def set_metric_progress(self) -> None:
        key_result = frappe.db.get_value(
            "OKR Key Result",
            self.key_result,
            ["metric_type", "metric_direction", "baseline_value", "target_value"],
            as_dict=True,
        )
        if not key_result:
            frappe.throw(_("The selected Action Item has no valid Key Result."))

        actual = flt(self.current_value)
        baseline = flt(key_result.baseline_value)
        target = flt(key_result.target_value)
        lower, upper = sorted((baseline, target))
        if key_result.metric_type == "Boolean":
            if actual not in (0, 1):
                frappe.throw(_("Current Value must be 0 or 1 for a Boolean Key Result."))
            progress = 100.0 if actual else 0.0
        else:
            if not lower <= actual <= upper:
                frappe.throw(_("Current Value must be between {0} and {1}.").format(lower, upper))
            if target == baseline:
                progress = 0.0
            elif key_result.metric_direction == "Decrease":
                progress = ((baseline - actual) / (baseline - target)) * 100.0
            else:
                progress = ((actual - baseline) / (target - baseline)) * 100.0

        self.progress = min(100.0, max(0.0, progress))
        self.progress_percent = self.progress

    def validate(self) -> None:
        ensure_required_link(self.action_item, "Action Item")
        ensure_required_link(self.key_result, "Key Result")
        ensure_percentage(self.progress, "Progress")
        ensure_required_link(self.action_status, "Status")

        if not self.achievements:
            frappe.throw(_("Progress Update is required."))

        if self.action_status not in ACTION_STATUS_MAP:
            frappe.throw(_("Please select a valid Status."))

        self.validate_action_item_assignment()
        self.validate_parent_plan_active()

        if self.name and frappe.db.exists("OKR Check In", self.name):
            previous_status = frappe.db.get_value("OKR Check In", self.name, "status")
            if previous_status == "Submitted":
                frappe.throw(_("Submitted Check-ins are read-only and cannot be modified."))

    def populate_from_action_item(self) -> None:
        if not frappe.db.exists("OKR Action Item", self.action_item):
            frappe.throw(_("Selected Action Item does not exist."))

        action = frappe.get_doc("OKR Action Item", self.action_item)
        self.validate_parent_plan_active(action)
        self.validate_action_item_assignment(action)

        key_result = frappe.get_doc("OKR Key Result", action.parent_key_result)
        objective = frappe.get_doc("OKR Objective", key_result.objective)
        plan = frappe.get_doc("OKR Plan", key_result.parent_plan)

        from okr_management.okr_management.doctype.okr_plan.okr_plan import get_plan_timeline

        start_date, end_date = get_plan_timeline(plan)
        day_count = date_diff(end_date, start_date) + 1

        self.key_result = key_result.name
        self.objective = objective.name
        self.parent_plan = plan.name
        self.financial_year = plan.financial_year
        self.company = plan.company
        self.department = getattr(action, "department", None)

        self.action_status = "In Progress" if action.status == "Open" else action.status

        self.action_item_title_context = action.action_item_title
        metric_unit = key_result.currency if key_result.metric_type == "Currency" else key_result.unit_of_measure
        unit_suffix = f" {metric_unit}" if metric_unit else ""
        self.progress_overview_context = _(
            "Current Progress: {0}{1} | Target: {2}{1}"
        ).format(flt(key_result.current_value, 2), unit_suffix, flt(key_result.target_value, 2))
        self.key_result_name_context = key_result.key_result_title
        self.key_result_description_context = key_result.description
        self.objective_name_context = objective.objective_title
        self.objective_description_context = objective.description
        self.plan_name_context = plan.plan_name
        self.plan_description_context = plan.description
        self.organization_context = plan.company
        self.financial_year_context = plan.financial_year
        self.timeline_preview_context = _("{0} to {1} ({2} Days)").format(
            formatdate(start_date), formatdate(end_date), day_count
        )
        self.assigned_to_context = (
            frappe.db.get_value("Employee", action.assigned_to, "employee_name")
            or action.assigned_to
        )

    def validate_parent_plan_active(self, action=None) -> None:
        action = action or frappe.get_doc("OKR Action Item", self.action_item)
        plan_name = action.parent_plan or frappe.db.get_value("OKR Key Result", action.parent_key_result, "parent_plan")
        if not plan_name or frappe.db.get_value("OKR Plan", plan_name, "status") != "Active":
            frappe.throw(_("Check-Ins are disabled until the parent OKR Plan is Active."))

    def validate_action_item_assignment(self, action=None) -> None:
        action = action or frappe.get_doc("OKR Action Item", self.action_item)
        if self.is_new() and action.status not in ACTIVE_ACTION_STATUSES:
            frappe.throw(_("Check-Ins can only be created for active Action Items."))

        employee = get_logged_in_employee(required=True)

        if action.assigned_to != employee:
            frappe.throw(_("You can only create Check-Ins for Action Items assigned to you."))

    def on_trash(self) -> None:
        if self.status == "Submitted":
            frappe.throw(_("Submitted Check-ins cannot be deleted."))

    def on_update(self) -> None:
        if self.action_item and frappe.db.exists("OKR Action Item", self.action_item):
            action = frappe.get_doc("OKR Action Item", self.action_item)
            action.progress = self.progress
            action.status = ACTION_STATUS_MAP[self.action_status]
            action.flags.ignore_permissions = True
            action.save()


        if self.key_result:
            frappe.db.set_value("OKR Key Result", self.key_result, "current_value", flt(self.current_value))
            from okr_management.utils.okr_calculations import recalculate_key_result_progress
            recalculate_key_result_progress(self.key_result)

    def after_insert(self) -> None:
        sync_checkin_latest_flags(self.action_item)

    def after_delete(self) -> None:
        if self.key_result:
            frappe.db.set_value("OKR Key Result", self.key_result, "current_value", flt(self.current_value))
            from okr_management.utils.okr_calculations import recalculate_key_result_progress
            recalculate_key_result_progress(self.key_result)
        sync_checkin_latest_flags(self.action_item)


def sync_checkin_latest_flags(action_item: str | None) -> None:
	if not action_item:
		return

	# Acquire exclusive row lock on the parent Action Item record to serialize concurrent operations
	frappe.db.get_value("OKR Action Item", action_item, "name", for_update=True)

	checkins = frappe.get_all(
		"OKR Check In",
		filters={"action_item": action_item},
		fields=["name", "is_latest"],
		order_by="checkin_date desc, creation desc",
	)
	if not checkins:
		return

	latest_name = checkins[0].name
	frappe.db.set_value("OKR Check In", latest_name, "is_latest", 1, update_modified=False)

	other_names = [c.name for c in checkins[1:]]
	if other_names:
		frappe.db.set_value(
			"OKR Check In",
			{"name": ["in", other_names]},
			"is_latest",
			0,
			update_modified=False
		)


def rebuild_all_checkin_latest_flags() -> None:
	action_items = frappe.get_all("OKR Check In", pluck="action_item", distinct=True)
	for action_item in action_items:
		sync_checkin_latest_flags(action_item)


def get_logged_in_employee(required: bool = True) -> str | None:
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user, "status": "Active"},
        "name",
    )
    if not employee and required:
        frappe.throw(_("Your user account is not linked to an active Employee."))
    return employee


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_assigned_action_items(doctype, txt, searchfield, start, page_len, filters):
    employee = get_logged_in_employee(required=False)

    if not employee:
        return []

    return frappe.db.sql(
        f"""
        select ai.name, ai.action_item_title
        from `tabOKR Action Item` ai
        inner join `tabOKR Plan` plan on plan.name = ai.parent_plan
        where ai.status in ('Open', 'In Progress', 'Blocked')
          and plan.status = 'Active'
          and ai.assigned_to = %(employee)s
          and (ai.name like %(txt)s or ai.action_item_title like %(txt)s)
        order by ai.modified desc
        limit %(start)s, %(page_len)s
        """,
        {
            "employee": employee,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
    )

@frappe.whitelist()
def get_action_item_context(action_item: str) -> dict:
    doc = frappe.new_doc("OKR Check In")
    doc.action_item = action_item
    doc.populate_from_action_item()
    metric = frappe.db.get_value(
        "OKR Key Result",
        doc.key_result,
        ["metric_type", "metric_direction", "baseline_value", "current_value", "target_value", "currency", "unit_of_measure", "target_progress"],
        as_dict=True,
    )
    doc.current_value = metric.current_value if metric.current_value is not None else (metric.baseline_value or 0)
    doc.progress = metric.target_progress or 0
    result = {
        fieldname: doc.get(fieldname)
        for fieldname in (
            "current_value",
            "progress",
            "key_result",
            "objective",
            "parent_plan",
            "financial_year",
            "company",
            "department",
            "action_status",
            "action_item_title_context",
            "progress_overview_context",
            "key_result_name_context",
            "key_result_description_context",
            "objective_name_context",
            "objective_description_context",
            "plan_name_context",
            "plan_description_context",
            "organization_context",
            "financial_year_context",
            "timeline_preview_context",
            "assigned_to_context",
        )
    }
    result["metric"] = metric
    return result
