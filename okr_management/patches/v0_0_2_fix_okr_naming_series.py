from __future__ import annotations

import frappe

SERIES = {
	"OKR Objective": "OKR-OBJ-.YYYY.-",
	"OKR Key Result": "OKR-KR-.YYYY.-",
	"OKR Check In": "OKR-CHECKIN-.YYYY.-",
	"OKR Objective Review": "OKR-REVIEW-.YYYY.-",
}


def execute() -> None:
	for doctype, series in SERIES.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		frappe.db.set_value("DocType", doctype, "autoname", "naming_series:", update_modified=False)
		frappe.db.set_value("DocType", doctype, "naming_rule", 'By "Naming Series" field', update_modified=False)
		field = frappe.db.exists("DocField", {"parent": doctype, "fieldname": "naming_series"})
		if field:
			frappe.db.set_value("DocField", field, {"options": series, "default": series, "reqd": 1}, update_modified=False)
		frappe.clear_cache(doctype=doctype)
