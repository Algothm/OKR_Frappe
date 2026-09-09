from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

MAX_ROWS = 100
MAX_COLUMNS = 30


def _can_read_file(file_doc) -> bool:
	if frappe.session.user == "Administrator":
		return True
	if file_doc.attached_to_doctype and file_doc.attached_to_name:
		return bool(frappe.has_permission(file_doc.attached_to_doctype, "read", doc=file_doc.attached_to_name))
	return file_doc.owner == frappe.session.user


def _display_value(value):
	if value is None:
		return ""
	if isinstance(value, (date, datetime)):
		return value.isoformat()
	return str(value)


@frappe.whitelist()
def get_spreadsheet_preview(file_url: str) -> dict:
	decoded_file_url = unquote(file_url)
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name and decoded_file_url != file_url:
		file_name = frappe.db.get_value("File", {"file_url": decoded_file_url}, "name")
	if not file_name:
		frappe.throw(_("The selected attachment could not be found."))
	file_doc = frappe.get_doc("File", file_name)
	if not _can_read_file(file_doc):
		frappe.throw(_("You do not have permission to preview this attachment."), frappe.PermissionError)

	extension = Path(file_doc.file_name or file_url).suffix.lower()
	content = file_doc.get_content()
	if extension in {".xlsx", ".xlsm"}:
		rows = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	elif extension == ".xls":
		rows = read_xls_file_from_attached_file(content)
	elif extension == ".csv":
		text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
		rows = list(csv.reader(io.StringIO(text)))
	else:
		frappe.throw(_("This file is not a supported spreadsheet."))

	# Formatted-but-empty spreadsheet cells must not widen the preview.
	normalized_rows = [list(row) for row in rows]
	while normalized_rows and not any(value not in (None, "") for value in normalized_rows[-1]):
		normalized_rows.pop()

	last_used_column = 0
	for row in normalized_rows:
		for index, value in enumerate(row, start=1):
			if value not in (None, ""):
				last_used_column = max(last_used_column, index)

	total_rows = len(normalized_rows)
	total_columns = last_used_column
	preview_columns = min(total_columns, MAX_COLUMNS)
	preview = [
		list(map(_display_value, row[:preview_columns]))
		for row in normalized_rows[:MAX_ROWS]
	]
	return {
		"rows": preview,
		"total_rows": total_rows,
		"total_columns": total_columns,
		"truncated": total_rows > MAX_ROWS or total_columns > MAX_COLUMNS,
	}
