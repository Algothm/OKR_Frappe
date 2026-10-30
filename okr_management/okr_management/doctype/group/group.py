from __future__ import annotations

import frappe
from frappe.model.document import Document

from okr_management.permissions import has_group_permission


class Group(Document):
	def check_permission(self, permtype="read", permlevel=None):
		if not has_group_permission(self, ptype=permtype):
			frappe.throw(
				frappe._("You do not have permission to perform this action on Group."),
				frappe.PermissionError,
			)
		return super().check_permission(permtype, permlevel)
