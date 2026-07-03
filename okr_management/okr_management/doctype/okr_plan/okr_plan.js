frappe.ui.form.on('OKR Plan', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		if (!frm.doc.company) {
			frm.set_value('company', frappe.defaults.get_user_default('Company') || '');
		}
	}
});