from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today


def ensure_title_editable_before_plan_start(
	doc: Any, title_field: str, plan_name: str | None = None
) -> None:
	"""Prevent renaming an existing OKR hierarchy record once its Plan has started."""
	if doc.is_new():
		return

	if doc.doctype == "OKR Plan":
		previous = doc.get_doc_before_save()
		previous_activation_date = previous.planned_activation_date if previous else None
		current_activation_date = doc.planned_activation_date
		if (
			previous_activation_date
			and getdate(previous_activation_date) <= getdate(today())
			and current_activation_date
			and getdate(current_activation_date) > getdate(today())
			and doc.has_value_changed("planned_activation_date")
		):
			frappe.throw(_("Planned Activation Date cannot be moved into the future after the Plan has started."))
		activation_dates = (previous_activation_date, current_activation_date)
	else:
		plan_name = plan_name or doc.get("parent_plan")
		activation_dates = (
			frappe.db.get_value("OKR Plan", plan_name, "planned_activation_date")
			if plan_name
			else None
		)
		activation_dates = (activation_dates,)

	if not doc.has_value_changed(title_field):
		return

	if any(
		activation_date and getdate(activation_date) <= getdate(today())
		for activation_date in activation_dates
	):
		frappe.throw(
			_("{0} cannot be changed on or after the Plan start date.").format(
				doc.meta.get_label(title_field) or title_field
			)
		)


def ensure_document_id_editable_before_plan_start(doc: Any, plan_name: str | None = None) -> None:
	"""Prevent renaming hierarchy document IDs once their Plan has started."""
	if doc.doctype == "OKR Plan":
		activation_date = doc.planned_activation_date
	else:
		plan_name = plan_name or doc.get("parent_plan")
		activation_date = (
			frappe.db.get_value("OKR Plan", plan_name, "planned_activation_date")
			if plan_name
			else None
		)
	if activation_date and getdate(activation_date) <= getdate(today()):
		frappe.throw(_("Document ID cannot be changed on or after the Plan start date."))


def ensure_date_range(start_date: Any, end_date: Any, label: str) -> None:
	if start_date and end_date and getdate(start_date) > getdate(end_date):
		frappe.throw(_("{0} start date cannot be after end date.").format(label))


def ensure_percentage(value: Any, field_label: str) -> None:
	percentage = flt(value)
	if percentage < 0 or percentage > 100:
		frappe.throw(_("{0} must be between 0 and 100.").format(field_label))


def ensure_required_link(value: Any, field_label: str) -> None:
	if not value:
		frappe.throw(_("{0} is required.").format(field_label))


def ensure_max_length(value: Any, field_label: str, max_length: int = 1000) -> None:
	if value is not None and len(str(value)) > max_length:
		frappe.throw(
			_("{0} cannot exceed {1} characters.").format(field_label, max_length)
		)


def ensure_valid_weight(weight: Any, field_label: str = "Weight") -> None:
	value = flt(weight)
	if value < 0 or value > 100:
		frappe.throw(_("{0} must be between 0 and 100.").format(field_label))


def ensure_child_rows(rows: list[dict[str, Any]] | None, field_label: str) -> None:
	if not rows:
		frappe.throw(_("{0} requires at least one row.").format(field_label))


def ensure_positive_integer(value: Any, field_label: str) -> None:
	if cint(value) <= 0:
		frappe.throw(_("{0} must be greater than zero.").format(field_label))
