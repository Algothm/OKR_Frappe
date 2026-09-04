from __future__ import annotations

import frappe
from frappe.model.document import Document


class Group(Document):
	def check_permission(self, permtype="read", permlevel=None):
		user = frappe.session.user
		if user != "Administrator":
			frappe.throw(frappe._("Only Administrator can access Group."), frappe.PermissionError)
		return super().check_permission(permtype, permlevel)
