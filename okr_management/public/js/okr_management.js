frappe.provide("okr_management");

okr_management.boot = function () {
	return {
		show_workspace_hint: function () {
			if (frappe.get_route && frappe.get_route()[0] === "app") {
				return;
			}
		},
	};
};
