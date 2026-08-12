frappe.listview_settings["OKR Key Result"] = {
	onload(listview) {
		const preferred_order = ["name", "key_result_title", "objective_title", "parent_plan"];
		const columns_by_field = new Map(
			listview.columns
				.filter((column) => column.df?.fieldname)
				.map((column) => [column.df.fieldname, column])
		);
		const fixed_columns = listview.columns.filter((column) => !column.df?.fieldname);
		const preferred_columns = preferred_order
			.map((fieldname) => columns_by_field.get(fieldname))
			.filter(Boolean);
        const id_column = columns_by_field.get("name");
        const title_column = columns_by_field.get("key_result_title");
        if (id_column) id_column.type = "Subject";
        if (title_column) title_column.type = "Field";
		const remaining_columns = listview.columns.filter(
			(column) => column.df?.fieldname && !preferred_order.includes(column.df.fieldname)
		);

		listview.columns = [...preferred_columns, ...fixed_columns, ...remaining_columns];
		listview.render_header(true);
	},
};
