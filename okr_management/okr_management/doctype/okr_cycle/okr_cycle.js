frappe.ui.form.on('OKR Cycle', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		if (!frm.doc.owner_user) {
			frm.set_value('owner_user', frappe.session.user);
		}
	}
});
