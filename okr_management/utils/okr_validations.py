from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


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
