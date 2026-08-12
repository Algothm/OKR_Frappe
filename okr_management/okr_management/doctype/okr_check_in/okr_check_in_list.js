frappe.listview_settings['OKR Check In'] = {
	onload(listview) {
		if (!frappe.route_options) {
			frappe.route_options = {};
		}
		if (frappe.route_options.is_latest === undefined) {
			frappe.route_options.is_latest = 1;
		}
        const field_order = ["name", "key_result", "action_item", "progress"];
        const existing_columns = new Map(
            listview.columns
                .filter((column) => column.df?.fieldname)
                .map((column) => [column.df.fieldname, column])
        );
        const preferred_columns = field_order
            .map((fieldname) => {
                if (existing_columns.has(fieldname)) return existing_columns.get(fieldname);
                const df = frappe.meta.get_docfield(listview.doctype, fieldname);
                return df ? { type: "Field", df } : null;
            })
            .filter(Boolean);
        const fixed_columns = listview.columns.filter((column) => !column.df?.fieldname);
        const remaining_columns = listview.columns.filter(
            (column) => column.df?.fieldname && !field_order.includes(column.df.fieldname)
        );
        listview.columns = [...preferred_columns, ...fixed_columns, ...remaining_columns];
        listview.render_header(true);
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
