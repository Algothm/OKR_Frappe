frappe.ui.form.on('OKR Sprint', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.toggle_reqd('parent_plan', true);
		frm.toggle_reqd('sprint_cycle', true);
		frm.toggle_reqd('quarter', frm.doc.sprint_cycle === 'Quarterly');
	},
	sprint_cycle(frm) {
		frm.toggle_reqd('quarter', frm.doc.sprint_cycle === 'Quarterly');
		if (frm.doc.sprint_cycle !== 'Quarterly') {
			frm.set_value('quarter', '');
		}
	}
});