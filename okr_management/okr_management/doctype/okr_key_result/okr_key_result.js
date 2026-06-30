frappe.ui.form.on('OKR Key Result', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('target_progress', 'read_only', 1);
		frm.set_df_property('current_value', 'read_only', 1);
		frm.set_df_property('confidence', 'read_only', 1);
		frm.set_df_property('status', 'read_only', 1);
		
		render_objective_summary(frm);
		render_kr_summary_widget(frm);
	},
	objective(frm) {
		if (frm.doc.objective) {
			frappe.db.get_value('OKR Objective', frm.doc.objective, ['owner_user', 'start_date', 'end_date']).then(r => {
				const objective = r.message || {};
				if (objective.owner_user && !frm.doc.owner_user) frm.set_value('owner_user', objective.owner_user);
				if (objective.owner_user && !frm.doc.assigned_by) frm.set_value('assigned_by', objective.owner_user);
				if (objective.start_date && !frm.doc.start_date) frm.set_value('start_date', objective.start_date);
				if (objective.end_date && !frm.doc.end_date) frm.set_value('end_date', objective.end_date);
				
				render_objective_summary(frm);
			});
		} else {
			frm.dashboard.clear_headline();
		}
	}
});

function render_objective_summary(frm) {
	if (!frm.doc.objective) {
		frm.dashboard.clear_headline();
		return;
	}
	frappe.db.get_value('OKR Objective', frm.doc.objective, ['description', 'department', 'level']).then(r => {
		const objective = r.message || {};
		const desc = objective.description || 'No description provided.';
		const dept = objective.level === 'Department' ? (objective.department || 'N/A') : 'Organization Level';
		
		const html = `
			<div class="okr-summary-card" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; padding: 16px 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);">
				<div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #e0f2fe; font-weight: 600; margin-bottom: 8px;">Parent Objective Context</div>
				<div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
					<div>
						<div style="font-size: 11px; color: #bae6fd; text-transform: uppercase;">Objective Description</div>
						<div style="font-size: 14px; font-weight: 500; color: #f0f9ff; margin-top: 4px; line-height: 1.4;">${desc}</div>
					</div>
					<div>
						<div style="font-size: 11px; color: #bae6fd; text-transform: uppercase;">Department / Level</div>
						<div style="font-size: 14px; font-weight: 600; color: #f0f9ff; margin-top: 4px;">${dept}</div>
					</div>
				</div>
			</div>
		`;
		frm.dashboard.set_headline_html(html);
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
