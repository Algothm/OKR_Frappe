frappe.ui.form.on('OKR Key Result', {
	onload(frm) {
		calculate_progress_preview(frm);
	},
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('cycle', 'read_only', 1);
		frm.set_df_property('target_progress', 'read_only', 1);
		frm.set_df_property('progress_updates', 'hidden', 1);
		frm.set_df_property('current_value', 'read_only', !frm.is_new());
		calculate_progress_preview(frm);
	},
	validate(frm) {
		calculate_progress_preview(frm);
	},
	objective(frm) {
		fill_from_objective(frm);
	},
	baseline_value(frm) {
		calculate_progress_preview(frm);
	},
	current_value(frm) {
		calculate_progress_preview(frm);
	},
	target_value(frm) {
		calculate_progress_preview(frm);
	}
});

function fill_from_objective(frm) {
	if (!frm.doc.objective) return;
	frappe.db.get_value('OKR Objective', frm.doc.objective, ['cycle', 'owner_user', 'start_date', 'end_date']).then(r => {
		const objective = r.message || {};
		if (objective.cycle) frm.set_value('cycle', objective.cycle);
		if (objective.owner_user && !frm.doc.owner_user) frm.set_value('owner_user', objective.owner_user);
		if (objective.start_date && !frm.doc.start_date) frm.set_value('start_date', objective.start_date);
		if (objective.end_date && !frm.doc.end_date) frm.set_value('end_date', objective.end_date);
	});
}

function calculate_progress_preview(frm) {
	const baseline = flt(frm.doc.baseline_value || 0);
	const current = flt(frm.doc.current_value || 0);
	const target = flt(frm.doc.target_value || 0);

	if (target === baseline) {
		set_progress_if_changed(frm, 0);
		frm.set_df_property(
			'target_progress',
			'description',
			__('Target Progress is calculated automatically. Target Value must differ from Baseline Value.')
		);
		return;
	}

	let progress = ((current - baseline) / (target - baseline)) * 100;
	progress = Math.max(0, Math.min(100, progress));
	progress = flt(progress, 3);

	set_progress_if_changed(frm, progress);
	frm.set_df_property(
		'target_progress',
		'description',
		__('Auto-calculated from Baseline Value, Current Value, and Target Value.')
	);
}

function set_progress_if_changed(frm, progress) {
	if (flt(frm.doc.target_progress, 3) !== flt(progress, 3)) {
		frm.set_value('target_progress', progress);
	} else {
		frm.refresh_field('target_progress');
	}
}
