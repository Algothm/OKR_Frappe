frappe.ui.form.on('OKR Cycle', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		if (!frm.doc.owner_user) {
			frm.set_value('owner_user', frappe.session.user);
		}
	},
	end_date(frm) {
		if (frm.doc.end_date && !frm.doc.review_deadline) {
			frm.set_value('review_deadline', frappe.datetime.add_days(frm.doc.end_date, 7));
		}
	}
});
