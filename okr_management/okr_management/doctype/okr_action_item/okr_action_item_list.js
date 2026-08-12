frappe.listview_settings["OKR Action Item"] = {
	onload(listview) {
		set_action_item_column_order(listview, [
			"name",
			"action_item_title",
			"parent_key_result",
			"assigned_to",
		]);
	},
};

function set_action_item_column_order(listview, field_order) {
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
    const id_column = preferred_columns.find((column) => column.df?.fieldname === "name");
    const title_column = preferred_columns.find(
        (column) => column.df?.fieldname === "action_item_title"
    );
    if (id_column) id_column.type = "Subject";
    if (title_column) title_column.type = "Field";
	const fixed_columns = listview.columns.filter((column) => !column.df?.fieldname);
	const remaining_columns = listview.columns.filter(
		(column) => column.df?.fieldname && !field_order.includes(column.df.fieldname)
	);

	listview.columns = [...preferred_columns, ...fixed_columns, ...remaining_columns];
	listview.render_header(true);
}
