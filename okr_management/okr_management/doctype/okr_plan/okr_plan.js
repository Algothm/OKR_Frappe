frappe.ui.form.on('OKR Plan', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
	}
});
