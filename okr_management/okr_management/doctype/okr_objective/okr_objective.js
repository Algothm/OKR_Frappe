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
		
		render_sprint_summary(frm);
	},
	sprint(frm) {
		if (frm.doc.sprint) {
			frappe.db.get_value('OKR Sprint', frm.doc.sprint, ['start_date', 'end_date', 'parent_plan', 'quarter', 'status']).then(r => {
				const sprint = r.message || {};
				if (sprint.start_date) frm.set_value('start_date', sprint.start_date);
				if (sprint.end_date) frm.set_value('end_date', sprint.end_date);
				
				if (sprint.parent_plan) {
					frappe.db.get_value('OKR Plan', sprint.parent_plan, 'financial_year').then(plan_res => {
						const fy = plan_res.message ? plan_res.message.financial_year : '';
						// Auto-populate company (Organization)
						const default_co = frappe.defaults.get_user_default("Company") || '';
						frm.set_value('company', default_co);
					});
				}
				render_sprint_summary(frm);
			});
		} else {
			frm.dashboard.clear_headline();
		}
	},
	level(frm) {
		frm.toggle_reqd('department', frm.doc.level === 'Department');
	}
});

function render_sprint_summary(frm) {
	if (!frm.doc.sprint) {
		frm.dashboard.clear_headline();
		return;
	}
	frappe.db.get_value('OKR Sprint', frm.doc.sprint, ['parent_plan', 'quarter', 'status']).then(r => {
		const sprint = r.message || {};
		const plan = sprint.parent_plan || 'N/A';
		const quarter = sprint.quarter || 'N/A';
		const status = sprint.status || 'Draft';
		
		let status_class = 'okr-status-draft';
		if (status === 'Active') status_class = 'okr-status-active';
		else if (status === 'Completed') status_class = 'okr-status-completed';
		else if (status === 'Closed') status_class = 'okr-status-completed';

		const html = `
			<div class="okr-summary-card" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff; padding: 16px 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);">
				<div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; font-weight: 600; margin-bottom: 8px;">Sprint Context Summary</div>
				<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px;">
					<div>
						<div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Parent Plan</div>
						<div style="font-size: 14px; font-weight: 600; color: #f8fafc; margin-top: 4px;">${plan}</div>
					</div>
					<div>
						<div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Quarter</div>
						<div style="font-size: 14px; font-weight: 600; color: #f8fafc; margin-top: 4px;">${quarter}</div>
					</div>
					<div>
						<div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Sprint Status</div>
						<div style="font-size: 14px; font-weight: 600; color: #f8fafc; margin-top: 4px;">
							<span class="okr-status-badge ${status_class}" style="padding: 2px 8px; border-radius: 9999px; font-size: 11px;">${status}</span>
						</div>
					</div>
				</div>
			</div>
		`;
		frm.dashboard.set_headline_html(html);
	});
}
