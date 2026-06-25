frappe.ui.form.on('OKR Objective', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('company', 'read_only', 1);
		frm.set_df_property('progress', 'read_only', 1);
		frm.set_df_property('confidence', 'read_only', 1);
		if (frm.is_new() && (!frm.doc.status || frm.doc.status === 'Completed')) {
			frm.set_value('status', 'Draft');
		}
		if (!frm.doc.owner_user) {
			frm.set_value('owner_user', frappe.session.user);
		}
	},
	cycle(frm) {
		fill_from_cycle(frm);
	}
});

function fill_from_cycle(frm) {
	if (!frm.doc.cycle) return;
	frappe.db.get_value('OKR Cycle', frm.doc.cycle, ['company', 'start_date', 'end_date']).then(r => {
		const cycle = r.message || {};
		if (cycle.company) frm.set_value('company', cycle.company);
		if (cycle.start_date) frm.set_value('start_date', cycle.start_date);
		if (cycle.end_date) frm.set_value('end_date', cycle.end_date);
		validate_objective_dates(frm);
	});
}

function validate_objective_dates(frm) {
	if (frm.doc.start_date && frm.doc.end_date && frm.doc.start_date > frm.doc.end_date) {
		frappe.msgprint({
			title: __('Invalid Objective Dates'),
			indicator: 'red',
			message: __('Objective Start Date cannot be after Objective End Date. Please reselect the OKR Cycle or correct the dates.')
		});
	}
}
