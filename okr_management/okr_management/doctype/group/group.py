from __future__ import annotations

import frappe
from frappe.model.document import Document

from okr_management.permissions import is_group_manager


class Group(Document):
	def check_permission(self, permtype="read", permlevel=None):
		if not is_group_manager():
			frappe.throw(
				frappe._("Only Administrator or OKR Admin can access Group."),
				frappe.PermissionError,
			)
		return super().check_permission(permtype, permlevel)
