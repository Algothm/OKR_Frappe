frappe.provide("okr_management");

(() => {
	const OKR_GROUPS = new Set(["Planning", "Execution", "Administration"]);

	function selector(name, parent) {
		return '.sidebar-item-container[item-name="' + CSS.escape(name) + '"][item-parent="' + CSS.escape(parent) + '"]';
	}

	function get_item(name, parent) {
		return jQuery(selector(name, parent)).first();
	}

	function bind_group_toggle(name) {
		const item = get_item(name, "OKR Management");
		if (item.length === 0 || item.data("okrGroupToggleBound")) return;

		item.data("okrGroupToggleBound", true);
		item.find("> .desk-sidebar-item > .item-anchor").on("click.okr_group_toggle", (event) => {
			event.preventDefault();
			event.stopImmediatePropagation();
			item.find("> .desk-sidebar-item .drop-icon").trigger("click");
		});
	}

	function bind_okr_sidebar() {
		OKR_GROUPS.forEach(bind_group_toggle);
	}

	function schedule_bind() {
		setTimeout(bind_okr_sidebar, 100);
		setTimeout(bind_okr_sidebar, 500);
	}

	jQuery(document).on("page-change route-change", schedule_bind);
	frappe.after_ajax(schedule_bind);

	jQuery(document).ready(() => {
		new MutationObserver(schedule_bind).observe(document.body, { childList: true, subtree: true });
		schedule_bind();
	});
})();
