from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from okr_management.utils.okr_validations import ensure_required_link


class OKRActionItem(Document):
    def before_validate(self) -> None:
        self._fill_from_key_result()
        if self.status == "Completed" and not self.completion_date:
            self.completion_date = nowdate()
        if self.status != "Completed" and self.completion_date:
            self.completion_date = None

    def validate(self) -> None:
        ensure_required_link(self.key_result, "Key Result")
        ensure_required_link(self.owner_user, "Owner User")
        if self.start_date and self.due_date and getdate(self.due_date) < getdate(self.start_date):
            frappe.throw("Action Item Due Date cannot be before Start Date.")
        self._warn_for_date_context()

    def _fill_from_key_result(self) -> None:
        if not self.key_result or not frappe.db.exists("OKR Key Result", self.key_result):
            return
        key_result = frappe.db.get_value(
            "OKR Key Result",
            self.key_result,
            ["objective", "cycle", "owner_user", "start_date", "end_date"],
            as_dict=True,
        )
        if not key_result:
            return
        if key_result.objective:
            self.objective = key_result.objective
        if key_result.cycle:
            self.cycle = key_result.cycle
        if key_result.owner_user and not self.owner_user:
            self.owner_user = key_result.owner_user
        if key_result.start_date and not self.start_date:
            self.start_date = key_result.start_date
        if key_result.end_date and not self.due_date:
            self.due_date = key_result.end_date
        if self.objective and frappe.db.exists("OKR Objective", self.objective):
            department = frappe.db.get_value("OKR Objective", self.objective, "department")
            if department:
                self.department = department

    def _warn_for_date_context(self) -> None:
        if not self.due_date:
            return
        if self.key_result and frappe.db.exists("OKR Key Result", self.key_result):
            kr = frappe.db.get_value("OKR Key Result", self.key_result, ["start_date", "end_date"], as_dict=True)
            if kr and ((kr.start_date and getdate(self.due_date) < getdate(kr.start_date)) or (kr.end_date and getdate(self.due_date) > getdate(kr.end_date))):
                frappe.msgprint("Action Item Due Date is outside the selected Key Result date range. This is allowed for execution planning.")
        if self.cycle and frappe.db.exists("OKR Cycle", self.cycle):
            cycle = frappe.db.get_value("OKR Cycle", self.cycle, ["start_date", "end_date"], as_dict=True)
            if cycle and ((cycle.start_date and getdate(self.due_date) < getdate(cycle.start_date)) or (cycle.end_date and getdate(self.due_date) > getdate(cycle.end_date))):
                frappe.msgprint("Action Item Due Date is outside the OKR Cycle date range. This is allowed, but please verify the plan.")
