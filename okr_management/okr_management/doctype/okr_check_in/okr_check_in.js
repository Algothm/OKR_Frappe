frappe.ui.form.on('OKR Check In', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('objective', 'read_only', 1);
		frm.set_df_property('cycle', 'read_only', 1);
		if (!frm.doc.reported_by) {
			frm.set_value('reported_by', frappe.session.user);
		}
		apply_manager_review_permissions(frm);
	},
	key_result(frm) {
		fill_from_key_result(frm);
	},
	reported_by(frm) {
		apply_manager_review_permissions(frm);
	}
});

function is_okr_manager() {
	return frappe.user.has_role('System Manager') || frappe.user.has_role('OKR Admin') || frappe.user.has_role('OKR Manager') || frappe.user.has_role('Team Lead');
}

function apply_manager_review_permissions(frm) {
	const can_review = is_okr_manager();
	frm.set_df_property('manager_review_section', 'hidden', !can_review);
	['manager_rating', 'manager_feedback', 'review_status'].forEach(field => {
		frm.set_df_property(field, 'read_only', !can_review);
		frm.set_df_property(field, 'hidden', !can_review);
	});
	frm.set_df_property('reported_by', 'read_only', !can_review);
}

function fill_from_key_result(frm) {
	if (!frm.doc.key_result) return;
	frappe.db.get_value('OKR Key Result', frm.doc.key_result, ['objective', 'cycle']).then(r => {
		const kr = r.message || {};
		if (kr.objective) frm.set_value('objective', kr.objective);
		if (kr.cycle) frm.set_value('cycle', kr.cycle);
		if (!frm.doc.reported_by) frm.set_value('reported_by', frappe.session.user);
	});
}
