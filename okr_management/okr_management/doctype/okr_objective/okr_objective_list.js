frappe.listview_settings["OKR Objective"] = {
	onload(listview) {
		$(listview.page.wrapper).addClass("okr-objective-list");

		const original_setup_columns = listview.setup_columns.bind(listview);
		listview.list_view_settings.total_fields = 5;
		listview.setup_columns = function () {
			const title_field = this.meta.title_field;
			this.meta.title_field = null;
			original_setup_columns();
			this.meta.title_field = title_field;

			const preferred = ["name", "objective_title", "level", "priority"];
			const by_field = new Map(
				this.columns
					.filter((column) => column.df?.fieldname)
					.map((column) => [column.df.fieldname, column])
			);
			const ordered = preferred.map((fieldname) => by_field.get(fieldname)).filter(Boolean);
			const fixed = this.columns.filter((column) => !column.df?.fieldname);
			this.columns = [...ordered, ...fixed];
		};

		listview.setup_columns();
		listview.render_header(true);
	},
};
