from __future__ import annotations

import frappe
from frappe.model.document import Document


class OKRActionItem(Document):
	def validate(self) -> None:
		pass

	def on_update(self) -> None:
		# If this action item is a child of a Key Result, trigger KR recalculation
		# so progress flows up: Action Item -> Key Result -> Objective -> Sprint -> Plan
		parent = getattr(self, "parent", None)
		parent_type = getattr(self, "parenttype", None)
		if parent and parent_type == "OKR Key Result" and frappe.db.exists("OKR Key Result", parent):
			kr_doc = frappe.get_doc("OKR Key Result", parent)
			kr_doc.flags.ignore_permissions = True
			kr_doc.save()
