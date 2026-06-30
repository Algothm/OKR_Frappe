frappe.ui.form.on('OKR Key Result', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('cycle', 'read_only', 1);
		frm.set_df_property('target_progress', 'read_only', 1);
		frm.set_df_property('current_value', 'read_only', 1);
		frm.set_df_property('confidence', 'read_only', 1);
		frm.set_df_property('status', 'read_only', 1);
		render_kr_summary_widget(frm);
	},
	objective(frm) {
		fill_from_objective(frm);
	}
});

function fill_from_objective(frm) {
	if (!frm.doc.objective) return;
	frappe.db.get_value('OKR Objective', frm.doc.objective, ['cycle', 'owner_user', 'start_date', 'end_date', 'department']).then(r => {
		const objective = r.message || {};
		if (objective.cycle) frm.set_value('cycle', objective.cycle);
		if (objective.owner_user && !frm.doc.owner_user) frm.set_value('owner_user', objective.owner_user);
		if (objective.owner_user && !frm.doc.assigned_by) frm.set_value('assigned_by', objective.owner_user);
		if (objective.start_date && !frm.doc.start_date) frm.set_value('start_date', objective.start_date);
		if (objective.end_date && !frm.doc.end_date) frm.set_value('end_date', objective.end_date);
		if (objective.department && !frm.doc.department) frm.set_value('department', objective.department);
	});
}

function render_kr_summary_widget(frm) {
	const $sidebar = frm.get_field('summary_sidebar_section') ? frm.get_field('summary_sidebar_section').$wrapper : null;
	if (!$sidebar) return;

	let $widget = $sidebar.find('.okr-custom-sidebar-widget');
	if (!$widget.length) {
		$widget = $('<div class="okr-custom-sidebar-widget"></div>').prependTo($sidebar);
	}

	const progress = flt(frm.doc.target_progress || 0);
	const status = frm.doc.status || 'Draft';
	const app_status = frm.doc.approval_status || 'Draft';

	let status_class = 'okr-status-draft';
	if (status === 'Active') status_class = 'okr-status-active';
	else if (status === 'At Risk') status_class = 'okr-status-atrisk';
	else if (status === 'Blocked') status_class = 'okr-status-blocked';
	else if (status === 'Achieved') status_class = 'okr-status-completed';

	let app_status_class = 'okr-status-draft';
	if (app_status === 'Approved') app_status_class = 'okr-status-active';
	else if (app_status === 'Pending Approval') app_status_class = 'okr-status-atrisk';
	else if (app_status === 'Rejected') app_status_class = 'okr-status-blocked';

	$widget.html(`
		<div class="okr-summary-widget">
			<div class="okr-summary-value">${progress.toFixed(1)}%</div>
			<div class="okr-summary-label">${__('Key Result Progress')}</div>
		</div>
		<div style="display:flex;justify-content:center;gap:8px;margin-bottom:16px;">
			<span class="okr-status-badge ${status_class}">${__(status)}</span>
			<span class="okr-status-badge ${app_status_class}">${__(app_status)}</span>
		</div>
	`);
}
