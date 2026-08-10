frappe.listview_settings['OKR Check In'] = {
	onload(listview) {
		if (!frappe.route_options) {
			frappe.route_options = {};
		}
		if (frappe.route_options.is_latest === undefined) {
			frappe.route_options.is_latest = 1;
		}
	},
	refresh(listview) {
		try {
			if (listview.filter_area && typeof listview.filter_area.add_filter === 'function') {
				const filters = (typeof listview.filter_area.get_filters === 'function')
					? listview.filter_area.get_filters()
					: [];
				const has_filter = filters.some(f => f[1] === 'is_latest');
				if (!has_filter) {
					listview.filter_area.add_filter('OKR Check In', 'is_latest', '=', '1');
				}
			}
		} catch (e) {
			console.error("Error setting default is_latest filter:", e);
		}
	}
};
