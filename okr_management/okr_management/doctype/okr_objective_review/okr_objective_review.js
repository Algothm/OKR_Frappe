frappe.ui.form.on('OKR Objective Review', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('sprint', 'read_only', 1);
		frm.set_df_property('self_rating', 'read_only', 1);
		if (!frm.doc.reviewer) {
			frm.set_value('reviewer', frappe.session.user);
		}
		apply_review_permissions(frm);
		derive_self_rating(frm);
	},
	objective(frm) {
		fill_from_objective(frm);
		derive_self_rating(frm);
	}
});

function is_okr_reviewer() {
	return frappe.user.has_role('System Manager') || frappe.user.has_role('OKR Admin') || frappe.user.has_role('Team Lead');
}

function apply_review_permissions(frm) {
	const can_review = is_okr_reviewer();
	['manager_rating', 'manager_feedback', 'rating', 'decision', 'review_status', 'next_actions'].forEach(field => {
		frm.set_df_property(field, 'read_only', !can_review);
	});
}

function fill_from_objective(frm) {
	if (!frm.doc.objective) return;
	frappe.db.get_value('OKR Objective', frm.doc.objective, ['sprint']).then(r => {
		const objective = r.message || {};
		if (objective.sprint) frm.set_value('sprint', objective.sprint);
		if (!frm.doc.reviewer) frm.set_value('reviewer', frappe.session.user);
	});
}


function derive_self_rating(frm) {
	if (!frm.doc.objective || frm.doc.self_rating) return;
	frappe.call({
		method: 'okr_management.okr_management.doctype.okr_objective_review.okr_objective_review.get_derived_self_rating',
		args: { objective: frm.doc.objective },
		callback(r) {
			if (r.message) {
				frm.set_value('self_rating', r.message);
			}
		}
	});
}
