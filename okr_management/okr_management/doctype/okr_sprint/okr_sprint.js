frappe.ui.form.on('OKR Sprint', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
	}
});
