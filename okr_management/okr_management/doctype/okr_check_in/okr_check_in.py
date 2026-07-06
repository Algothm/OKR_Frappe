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
		self.status = self.status or "Draft"

		if self.key_result and frappe.db.exists("OKR Key Result", self.key_result):
			key_result = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				[
					"objective",
					"parent_sprint",
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
				self.parent_sprint = key_result.parent_sprint
				self.parent_plan = key_result.parent_plan
				self.financial_year = key_result.financial_year
				self.company = key_result.company
				self.department = key_result.department

				# Auto-calculate progress based on raw current_value and direction
				baseline = flt(key_result.baseline_value)
				target = flt(key_result.target_value)
				current = flt(self.current_value)

				if target == baseline:
					self.progress = 0.0
				elif key_result.metric_direction == "Decrease":
					self.progress = min(100.0, max(0.0, ((baseline - current) / (baseline - target)) * 100.0))
				else:
					self.progress = min(100.0, max(0.0, ((current - baseline) / (target - baseline)) * 100.0))

				self.progress_percent = self.progress

	def validate(self) -> None:
		ensure_required_link(self.key_result, "Key Result")
		ensure_required_link(self.reported_by, "Reported By")
		ensure_percentage(self.progress, "Progress")

		if self.key_result:
			kr_data = frappe.db.get_value(
				"OKR Key Result",
				self.key_result,
				[
					"objective",
					"parent_sprint",
					"parent_plan",
					"start_date",
					"end_date",
					"status",
				],
				as_dict=True,
			)
			if not kr_data:
				frappe.throw(_("Parent Key Result does not exist."))

			# Block all check-ins if Parent Key Result is not Active
			if kr_data.status != "Active":
				frappe.throw(
					_(
						"Check-ins are only allowed when the Parent Key Result is Active (current status: {0})."
					).format(kr_data.status)
				)

			# Enforce that parent Key Result has valid Parent Objective, Parent Sprint, and Parent Plan relationships
			if not kr_data.objective or not kr_data.parent_sprint or not kr_data.parent_plan:
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

			# Enforce duplicate Submitted check-in per calendar day
			if self.status == "Submitted":
				existing_submitted = frappe.db.get_value(
					"OKR Check In",
					{
						"key_result": self.key_result,
						"status": "Submitted",
						"checkin_date": self.checkin_date,
						"name": ["!=", self.name or ""],
					},
					"name",
				)
				if existing_submitted:
					frappe.throw(
						_("Only one Submitted Check-in is allowed per Key Result per calendar day.")
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
		# Update Action Items progress and status back to the Key Result
		if self.key_result and frappe.db.exists("OKR Key Result", self.key_result):
			key_result = frappe.get_doc("OKR Key Result", self.key_result)
			updated_kr = False
			for ci_item in getattr(self, "action_items", []):
				for kr_item in key_result.action_items:
					if kr_item.action_item_title == ci_item.action_item_title:
						if kr_item.progress != ci_item.progress or kr_item.status != ci_item.status:
							kr_item.progress = ci_item.progress
							kr_item.status = ci_item.status
							kr_item.notes = ci_item.notes
							kr_item.due_date = ci_item.due_date
							updated_kr = True
							break
			if updated_kr:
				key_result.flags.ignore_permissions = True
				key_result.save()

		# Sync checkin progress values
		if self.status == "Submitted":
			sync_checkin_progress(self)
