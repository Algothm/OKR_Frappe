from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt, nowdate

from okr_management.utils.okr_calculations import sync_checkin_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


class OKRCheckIn(Document):
	def before_validate(self) -> None:
		if not self.reported_by:
			self.reported_by = frappe.session.user
		if not self.checkin_date:
			self.checkin_date = nowdate()
		self.status = "Submitted"

		if self.key_result and frappe.db.exists("OKR Key Result", self.key_result):
			key_result = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				[
					"objective",
					"parent_plan",
					"parent_plan",
					"financial_year",
					"company",
					"department",
					"baseline_value",
					"target_value",
					"metric_direction",
				],
				as_dict=True,
			)
			if key_result:
				self.objective = key_result.objective
				self.parent_plan = key_result.parent_plan
				self.parent_plan = key_result.parent_plan
				self.financial_year = key_result.financial_year
				self.company = key_result.company
				self.department = key_result.department

				self.progress = min(100.0, max(0.0, flt(self.progress)))
				self.progress_percent = self.progress
				self.current_value = self.progress

	def validate(self) -> None:
		ensure_required_link(self.key_result, "Key Result")
		ensure_required_link(self.reported_by, "Reported By")
		ensure_percentage(self.progress, "Progress")
		if not self.achievements:
			frappe.throw(_("Description / Update is required."))

		if self.key_result:
			kr_data = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				[
					"objective",
					"parent_plan",
					"parent_plan",
					"start_date",
					"end_date",
					"status",
				],
				as_dict=True,
			)
			if not kr_data:
				frappe.throw(_("Parent Key Result does not exist."))

			# Workspace task check-ins are allowed while a Key Result is Draft or Active.
			if kr_data.status not in {"Draft", "Active"}:
				frappe.throw(
					_(
						"Check-ins are only allowed when the Parent Key Result is Draft or Active (current status: {0})."
					).format(kr_data.status)
				)

			# Enforce that parent Key Result has valid Parent Objective, Parent Sprint, and Parent Plan relationships
			if not kr_data.objective or not kr_data.parent_plan or not kr_data.parent_plan:
				frappe.throw(
					_(
						"Check-in cannot be created or submitted because the parent Key Result does not have valid Parent Objective, Parent Sprint, and Parent Plan relationships."
					)
				)

			# Check-in Date must remain inside Parent Key Result date range
			if self.checkin_date:
				checkin_d = getdate(self.checkin_date)
				if kr_data.start_date and checkin_d < getdate(kr_data.start_date):
					frappe.throw(
						_("Check-in Date cannot be before the Key Result Start Date ({0}).").format(
							kr_data.start_date
						)
					)
				if kr_data.end_date and checkin_d > getdate(kr_data.end_date):
					frappe.throw(
						_("Check-in Date cannot be after the Key Result End Date ({0}).").format(
							kr_data.end_date
						)
					)

			# Future Date Check for Submitted check-ins
			if self.status == "Submitted" and self.checkin_date:
				if getdate(self.checkin_date) > getdate(nowdate()):
					frappe.throw(_("Submitted check-ins cannot have a future check-in date."))

			# Check-in Date cannot be earlier than the latest Submitted Check-in for that Key Result
			latest_date = frappe.db.get_value(
				"OKR Check In",
				{
					"key_result": self.key_result,
					"status": "Submitted",
					"name": ["!=", self.name or ""],
				},
				"checkin_date",
				order_by="checkin_date desc",
			)
			if latest_date and self.checkin_date and getdate(self.checkin_date) < getdate(latest_date):
				frappe.throw(
					_(
						"Check-in Date cannot be earlier than the latest Submitted Check-in date ({0}) for this Key Result."
					).format(latest_date)
				)

		# Immutability of Submitted check-ins
		if self.name and frappe.db.exists("OKR Check In", self.name):
			prev_status = frappe.db.get_value("OKR Check In", self.name, "status")
			if prev_status == "Submitted":
				frappe.throw(_("Submitted Check-ins are read-only and cannot be modified."))

	def on_trash(self) -> None:
		if self.status == "Submitted":
			frappe.throw(_("Submitted Check-ins cannot be deleted."))

	def on_update(self) -> None:
		if self.action_item and frappe.db.exists("OKR Action Item", self.action_item):
			action_item = frappe.get_doc("OKR Action Item", self.action_item)
			new_status = "Completed" if flt(self.progress) >= 100 else action_item.status
			if flt(action_item.progress) != flt(self.progress) or action_item.status != new_status:
				action_item.progress = self.progress
				action_item.status = new_status
				action_item.flags.ignore_permissions = True
				action_item.save()

		if self.status == "Submitted":
			sync_checkin_progress(self)

		if self.key_result:
			from okr_management.utils.okr_calculations import recalculate_key_result_progress
			recalculate_key_result_progress(self.key_result)

	def after_delete(self) -> None:
		if self.key_result:
			from okr_management.utils.okr_calculations import recalculate_key_result_progress
			recalculate_key_result_progress(self.key_result)



