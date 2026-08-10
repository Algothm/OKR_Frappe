frappe.pages['okr-executive-attention'].on_page_load = function(wrapper) {
	new OKRExecutiveAttention(wrapper);
};

class OKRExecutiveAttention {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('OKR Executive Attention'),
			single_column: true,
			card_layout: true,
		});
		this.page.set_primary_action(__('Refresh'), () => this.refresh(), 'refresh');
		this.page.add_action_item(__('Generate Executive Report'), () => {
			frappe.set_route('okr-executive-report');
		});
		this.$body = $(`<div class="okr-executive-attention"></div>`).appendTo(this.page.main);
		this.refresh();
	}

	refresh() {
		this.$body.html(`
			<div style="display:flex;align-items:center;gap:10px;padding:32px;color:var(--text-muted);">
				<div class="loading-indicator" style="width:20px;height:20px;border:2px solid var(--border-color);border-top-color:var(--primary);border-radius:50%;animation:okr-spin 0.8s linear infinite;"></div>
				<span>${__('Loading OKR health insights...')}</span>
			</div>
		`);
		frappe.call({
			method: 'okr_management.insights.get_executive_attention',
			callback: (r) => this.render(r.message || {}),
			error: () => this.$body.html(`
				<div style="padding:24px;">
					<div class="alert alert-danger">${__('Unable to load OKR insights. Please refresh or check server logs.')}</div>
				</div>
			`),
		});
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? '' : String(value));
	}

	render(data) {
		const summary = data.summary || {};
		const now = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
		const cards = [
			{label: "Today's Attention", value: summary.todays_attention, color: 'orange', icon: '⚡'},
			{label: 'Critical Objectives', value: summary.critical_objectives, color: 'red', icon: '🔴'},
			{label: 'Objectives At Risk', value: summary.objectives_at_risk, color: 'red', icon: '⚠️'},
			{label: 'Upcoming Deadlines', value: summary.upcoming_deadlines, color: 'yellow', icon: '📅'},
			{label: 'Pending Reviews', value: summary.pending_reviews, color: 'blue', icon: '📋'},
			{label: 'Missed Check-ins', value: summary.missed_checkins, color: 'orange', icon: '⏰'},
			{label: 'Low Confidence KRs', value: summary.low_confidence_key_results, color: 'red', icon: '📉'},
			{label: 'Inactive Owners', value: summary.inactive_owners, color: 'gray', icon: '👤'},
			{label: 'Avg Company Progress', value: `${summary.average_company_progress || 0}%`, color: 'green', icon: '📈'},
		];

		this.$body.html(`
			<style>
				@keyframes okr-spin { to { transform: rotate(360deg); } }
				@keyframes okr-bar-grow { from { width: 0; } }
				.okr-executive-attention { padding: 4px 0 24px; }
				.okr-refresh-ts { font-size:11px; color:var(--text-muted); text-align:right; padding:0 4px 10px; }
				.okr-card-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap:14px; margin-bottom:24px; }
				.okr-kpi-card { background: var(--card-bg); border:1px solid var(--border-color); border-radius:14px; padding:18px 18px 14px; box-shadow: var(--shadow-sm); position:relative; overflow:hidden; transition:box-shadow 0.2s, transform 0.15s; cursor:default; }
				.okr-kpi-card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
				.okr-kpi-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; border-radius:14px 14px 0 0; }
				.okr-kpi-card.color-red::before { background: linear-gradient(90deg,#ef4444,#dc2626); }
				.okr-kpi-card.color-orange::before { background: linear-gradient(90deg,#f97316,#ea580c); }
				.okr-kpi-card.color-yellow::before { background: linear-gradient(90deg,#f59e0b,#d97706); }
				.okr-kpi-card.color-green::before { background: linear-gradient(90deg,#10b981,#059669); }
				.okr-kpi-card.color-blue::before { background: linear-gradient(90deg,#3b82f6,#2563eb); }
				.okr-kpi-card.color-gray::before { background: linear-gradient(90deg,#94a3b8,#64748b); }
				.okr-kpi-card .okr-card-icon { font-size:18px; margin-bottom:8px; display:block; }
				.okr-kpi-card .okr-card-label { color: var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px; }
				.okr-kpi-card .okr-card-value { font-size:30px; font-weight:700; line-height:1; color: var(--heading-color); }
				.okr-kpi-card.color-red .okr-card-value { color: #dc2626; }
				.okr-kpi-card.color-orange .okr-card-value { color: #ea580c; }
				.okr-kpi-card.color-green .okr-card-value { color: #059669; }
				.okr-section { background: var(--card-bg); border:1px solid var(--border-color); border-radius:14px; padding:20px 20px 16px; margin-bottom:18px; box-shadow: var(--shadow-sm); }
				.okr-section-header { display:flex; align-items:center; gap:8px; margin-bottom:14px; }
				.okr-section-header h3 { margin:0; font-size:16px; font-weight:600; }
				.okr-section-badge { font-size:11px; font-weight:600; padding:2px 8px; border-radius:999px; background:var(--bg-light-gray); color:var(--text-muted); }
				.okr-table { width:100%; border-collapse:collapse; }
				.okr-table th { padding:8px 10px; border-bottom:2px solid var(--border-color); text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--text-muted); white-space:nowrap; }
				.okr-table td { padding:10px 10px; border-bottom:1px solid var(--border-color); vertical-align:top; font-size:13px; }
				.okr-table tr:last-child td { border-bottom:none; }
				.okr-table tr:hover td { background: var(--bg-light-gray); }
				.okr-pill { display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:600; padding:3px 9px; border-radius:999px; white-space:nowrap; }
				.okr-pill-critical { background:#fee2e2; color:#991b1b; }
				.okr-pill-high { background:#ffedd5; color:#9a3412; }
				.okr-pill-medium { background:#fef9c3; color:#854d0e; }
				.okr-pill-low { background:#dcfce7; color:#166534; }
				.okr-pill-default { background:#e2e8f0; color:#334155; }
				.okr-progressbar { height:7px; border-radius:999px; background:var(--border-color); overflow:hidden; margin-top:5px; }
				.okr-progressbar-fill { display:block; height:100%; border-radius:999px; background:linear-gradient(90deg,#2563eb,#10b981); animation: okr-bar-grow 0.8s ease-out; }
				.okr-progressbar-fill.danger { background:linear-gradient(90deg,#ef4444,#dc2626); }
				.okr-progressbar-fill.warning { background:linear-gradient(90deg,#f97316,#f59e0b); }
				.okr-actions-list { list-style:none; margin:0; padding:0; }
				.okr-actions-list li { display:flex; align-items:flex-start; gap:10px; padding:10px 0; border-bottom:1px solid var(--border-color); font-size:13px; }
				.okr-actions-list li:last-child { border-bottom:none; padding-bottom:0; }
				.okr-actions-list li::before { content:'→'; color:var(--primary); font-weight:700; flex-shrink:0; margin-top:1px; }
				.okr-empty-state { text-align:center; padding:28px 16px; color:var(--text-muted); font-size:13px; }
				.okr-empty-state .okr-empty-icon { font-size:28px; margin-bottom:8px; }
				.okr-dept-row { padding:10px 0; border-bottom:1px solid var(--border-color); }
				.okr-dept-row:last-child { border-bottom:none; }
				.okr-dept-meta { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px; }
				.okr-dept-name { font-weight:600; font-size:14px; }
				.okr-dept-stats { font-size:12px; color:var(--text-muted); }
				.okr-alignment-node { border-left: 2px solid var(--border-color); margin: 8px 0 8px 14px; padding-left: 12px; }
				.okr-alignment-kr { margin: 6px 0 6px 28px; color: var(--text-muted); font-size:12px; }
				.okr-badge { display:inline-block; font-size:10px; font-weight:600; padding:2px 6px; border-radius:4px; background:var(--bg-light-gray); color:var(--text-muted); margin-right:5px; text-transform:uppercase; letter-spacing:.04em; }
			</style>
			<div class="okr-refresh-ts">${__('Last refreshed')}: ${this.esc(now)}</div>
			<div class="okr-card-grid">${cards.map(c => this.kpiCard(c)).join('')}</div>
			${this.actionsSection(data.recommended_actions || [])}
			${this.reviewRatingSignals(data.latest_review_ratings || [], data.review_rating_summary || {})}
			${this.actionItemSignals(data.action_item_signals || {})}
			${this.tableSection('Critical Objectives / KRs', data.critical_objectives || [], 'critical')}
			${this.tableSection('Objectives At Risk', data.at_risk_objectives || [], 'risk')}
			${this.tableSection('Upcoming Deadlines', data.upcoming_deadlines || [], 'deadline')}
			${this.tableSection('Missed Check-ins', data.missed_checkins || [], 'missed')}
			${this.tableSection('Low Confidence Key Results', data.low_confidence_key_results || [], 'lowconf')}
			${this.inactiveOwners(data.inactive_owners || [])}
			${this.departmentPerformance(data.department_performance || [])}
			${this.alignmentView(data.alignment_tree || [])}
		`);
	}

	kpiCard({label, value, color, icon}) {
		return `
			<div class="okr-kpi-card color-${this.esc(color)}">
				<span class="okr-card-icon">${icon || ''}</span>
				<div class="okr-card-label">${this.esc(__(label))}</div>
				<div class="okr-card-value">${this.esc(value ?? 0)}</div>
			</div>`;
	}

	riskPill(riskLevel) {
		const map = {Critical: 'critical', High: 'high', Medium: 'medium', Low: 'low'};
		const cls = map[riskLevel] || 'default';
		return `<span class="okr-pill okr-pill-${cls}">${this.esc(riskLevel)}</span>`;
	}

	progressCell(progress) {
		const pct = Math.max(0, Math.min(100, progress || 0));
		const cls = pct < 40 ? 'danger' : pct < 65 ? 'warning' : '';
		return `<div>${this.esc(pct)}%</div><div class="okr-progressbar"><span class="okr-progressbar-fill${cls ? ' ' + cls : ''}" style="width:${pct}%"></span></div>`;
	}

	actionsSection(actions) {
		if (!actions.length) return '';
		return `
			<div class="okr-section">
				<div class="okr-section-header">
					<h3>${__('Recommended Actions')}</h3>
					<span class="okr-section-badge">${actions.length}</span>
				</div>
				<ul class="okr-actions-list">
					${actions.map(a => `<li>${this.esc(a)}</li>`).join('')}
				</ul>
			</div>`;
	}

	tableSection(title, rows, type) {
		const emptyMessages = {
			critical: {icon: '✅', msg: __('No critical objectives. Great news!')},
			risk: {icon: '🟢', msg: __('All objectives are on track.')},
			deadline: {icon: '📆', msg: __('No upcoming deadlines in the next 14 days.')},
			missed: {icon: '✓', msg: __('All owners have recent check-ins.')},
			lowconf: {icon: '💪', msg: __('All key results have healthy confidence levels.')},
		};
		const empty = emptyMessages[type] || {icon: '✓', msg: __('No items found.')};
		const emptyHtml = `<div class="okr-empty-state"><div class="okr-empty-icon">${empty.icon}</div>${empty.msg}</div>`;

		return `
			<div class="okr-section">
				<div class="okr-section-header">
					<h3>${this.esc(__(title))}</h3>
					<span class="okr-section-badge">${rows.length}</span>
				</div>
				${rows.length ? `
				<div class="table-responsive">
					<table class="okr-table">
						<thead><tr>
							<th>${__('Title')}</th>
							<th>${__('Owner')}</th>
							<th>${__('Progress')}</th>
							<th>${__('Confidence')}</th>
							<th>${__('Risk')}</th>
							<th>${__('Reason')}</th>
							<th>${__('Action')}</th>
						</tr></thead>
						<tbody>${rows.map(row => `<tr>
							<td><a href="${this.recordRoute(row)}" style="font-weight:500;">${this.esc(row.title)}</a><br><small class="text-muted">${this.esc(row.record)}</small></td>
							<td>${this.esc(row.owner || '—')}</td>
							<td style="min-width:110px">${this.progressCell(row.progress)}</td>
							<td>${this.esc(row.confidence)}</td>
							<td>${this.riskPill(row.risk_level)}</td>
							<td style="max-width:180px;font-size:12px;">${this.esc(row.reason)}</td>
							<td style="max-width:180px;font-size:12px;">${this.esc(row.recommended_action)}</td>
						</tr>`).join('')}</tbody>
					</table>
				</div>` : emptyHtml}
			</div>`;
	}

	inactiveOwners(rows) {
		return `
			<div class="okr-section">
				<div class="okr-section-header">
					<h3>${__('Inactive Owners')}</h3>
					<span class="okr-section-badge">${rows.length}</span>
				</div>
				${rows.length ? `<ul class="okr-actions-list">${rows.map(row =>
					`<li><div><b>${this.esc(row.owner)}</b> — ${__('Last check-in')}: <span class="text-muted">${this.esc(row.last_checkin_date || __('Never'))}</span><br><small>${this.esc(row.recommended_action)}</small></div></li>`
				).join('')}</ul>` : `<div class="okr-empty-state"><div class="okr-empty-icon">👥</div>${__('Everyone has recent updates.')}</div>`}
			</div>`;
	}

	departmentPerformance(rows) {
		if (!rows.length) return '';
		return `
			<div class="okr-section">
				<div class="okr-section-header">
					<h3>${__('Department Performance')}</h3>
					<span class="okr-section-badge">${rows.length} ${__('depts')}</span>
				</div>
				${rows.map(row => {
					const pct = Math.max(0, Math.min(100, row.average_progress || 0));
					const cls = pct < 40 ? 'danger' : pct < 65 ? 'warning' : '';
					return `
					<div class="okr-dept-row">
						<div class="okr-dept-meta">
							<span class="okr-dept-name">${this.esc(row.department)}</span>
							<span class="okr-dept-stats">${this.esc(pct)}% &middot; ${this.esc(row.objective_count)} ${__('objectives')} &middot; <span style="color:${row.at_risk ? '#dc2626' : 'inherit'}">${this.esc(row.at_risk)} ${__('at risk')}</span></span>
						</div>
						<div class="okr-progressbar"><span class="okr-progressbar-fill${cls ? ' ' + cls : ''}" style="width:${pct}%"></span></div>
					</div>`;
				}).join('')}
			</div>`;
	}

	alignmentView(companies) {
		return `
			<div class="okr-section">
				<div class="okr-section-header">
					<h3>${__('Alignment View')}</h3>
				</div>
				${!companies.length ? `<div class="okr-empty-state"><div class="okr-empty-icon">🗂</div>${__('No aligned OKRs found.')}</div>` : `
				<p class="text-muted" style="font-size:12px;margin-bottom:14px;">${__('Company → Department → Objective hierarchy → Key Results')}</p>
				${companies.map(company => `
					<div style="margin-bottom:16px;">
						<div style="font-weight:700;font-size:15px;margin-bottom:8px;">🏢 ${this.esc(company.company)}</div>
						${(company.departments || []).map(dept => `
							<div style="margin:8px 0 12px 0;">
								<span class="okr-badge">${__('Dept')}</span><b>${this.esc(dept.department)}</b>
								${(dept.objectives || []).map(obj => this.alignmentNode(obj)).join('')}
							</div>`).join('')}
					</div>`).join('')}`}
			</div>`;
	}

	alignmentNode(node) {
		const href = this.recordRoute(node);
		const pct = Math.max(0, Math.min(100, node.progress || 0));
		const cls = pct < 40 ? 'danger' : pct < 65 ? 'warning' : '';
		return `
			<div class="okr-alignment-node">
				<div style="margin-bottom:4px;">
					<span class="okr-badge">${this.esc(node.objective_type || __('Obj'))}</span>
					<a href="${href}" style="font-weight:500;">${this.esc(node.title)}</a>
					<small class="text-muted">${this.esc(node.record)}</small>
				</div>
				<div class="text-muted" style="font-size:12px;">
					${__('Owner')}: ${this.esc(node.owner || '—')} &middot;
					${__('Status')}: ${this.esc(node.status || '—')} &middot;
					${__('Progress')}: ${this.esc(node.progress || 0)}% &middot;
					${__('Confidence')}: ${this.esc(node.confidence || 0)}
				</div>
				<div class="okr-progressbar" style="margin-top:5px;"><span class="okr-progressbar-fill${cls ? ' ' + cls : ''}" style="width:${pct}%"></span></div>
				${(node.key_results || []).map(kr => this.alignmentKeyResult(kr)).join('')}
				${(node.children || []).map(child => this.alignmentNode(child)).join('')}
			</div>`;
	}

	alignmentKeyResult(kr) {
		const pct = Math.max(0, Math.min(100, kr.progress || 0));
		const cls = pct < 40 ? 'danger' : pct < 65 ? 'warning' : '';
		return `
			<div class="okr-alignment-kr">
				<span class="okr-badge" style="background:#dbeafe;color:#1d4ed8;">KR</span>
				<a href="${this.recordRoute(kr)}">${this.esc(kr.title)}</a>
				<small class="text-muted">${this.esc(kr.record)}</small>
				<div>${__('Owner')}: ${this.esc(kr.owner || '—')} &middot; ${__('Progress')}: ${this.esc(pct)}% &middot; ${__('Confidence')}: ${this.esc(kr.confidence || 0)}</div>
				<div class="okr-progressbar"><span class="okr-progressbar-fill${cls ? ' ' + cls : ''}" style="width:${pct}%"></span></div>
			</div>`;
	}

actionItemSignals(data = {}) {
const summary = data.summary || {};
const rows = [
...(data.blocked || []).map(row => ({...row, signal: __('Blocked')})),
...(data.overdue || []).map(row => ({...row, signal: __('Overdue')})),
...(data.due_soon || []).map(row => ({...row, signal: __('Due Soon')})),
];
const unique = [];
const seen = new Set();
rows.forEach(row => {
if (!seen.has(row.name)) {
seen.add(row.name);
unique.push(row);
}
});
return `
<div class="okr-section">
<div class="okr-section-header">
<h3>${__('Action Item Signals')}</h3>
<span class="okr-section-badge">${this.esc(unique.length)}</span>
</div>
<div class="text-muted" style="font-size:12px;margin-bottom:12px;">
${__('Blocked')}: ${this.esc(summary.blocked || 0)} · ${__('Overdue')}: ${this.esc(summary.overdue || 0)} · ${__('Due Soon')}: ${this.esc(summary.due_soon || 0)} · ${__('Open')}: ${this.esc(summary.total_open || 0)}
</div>
${unique.length ? `
<div class="table-responsive">
<table class="okr-table">
<thead><tr>
<th>${__('Signal')}</th>
<th>${__('Action Item')}</th>
<th>${__('Key Result')}</th>
<th>${__('Owner')}</th>
<th>${__('Status')}</th>
<th>${__('Priority')}</th>
<th>${__('Due Date')}</th>
<th>${__('Action')}</th>
</tr></thead>
<tbody>${unique.map(row => `<tr style="${row.status === 'Blocked' ? 'background:#fff7ed;' : ''}">
<td>${this.esc(row.signal)}</td>
<td><a href="/app/okr-action-item/${encodeURIComponent(row.name || '')}" style="font-weight:500;">${this.esc(row.action_item_title || row.name)}</a><br><small class="text-muted">${this.esc(row.name || '')}</small></td>
<td>${this.esc(row.key_result_title || row.key_result || '—')}</td>
<td>${this.esc(row.owner_user || '—')}</td>
<td>${this.esc(row.status || '—')}</td>
<td>${this.esc(row.priority || '—')}</td>
<td>${this.esc(row.due_date || '—')}</td>
<td style="max-width:220px;font-size:12px;">${this.esc(row.recommended_action || '')}</td>
</tr>`).join('')}</tbody>
</table>
</div>` : `<div class="okr-empty-state"><div class="okr-empty-icon">✓</div>${__('No blocked, overdue, or due-soon action items.')}</div>`}
</div>`;
}

	reviewRatingSignals(rows, summary = {}) {
		const issueCount = summary.rating_issues_count || 0;
		const notice = issueCount
			? `${issueCount} ${__('rating issue(s) need attention.')}`
			: __('No rating alignment issues found, but latest review ratings are shown below.');
		return `
			<div class="okr-section">
				<div class="okr-section-header">
					<h3>${__('Review Rating Signals')}</h3>
					<span class="okr-section-badge">${rows.length}</span>
				</div>
				<div class="text-muted" style="font-size:12px;margin-bottom:12px;">
					${this.esc(notice)} ${__('Total Reviews')}: ${this.esc(summary.total_reviews || 0)} · ${__('Average Self Rating')}: ${this.esc(summary.avg_self_rating || 0)} / 5 · ${__('Average Manager Rating')}: ${this.esc(summary.avg_manager_rating || 0)} / 5 · ${__('Average Overall Rating')}: ${this.esc(summary.avg_overall_rating || 0)} / 5 · ${__('Rating Issues Count')}: ${this.esc(issueCount)}
				</div>
				${rows.length ? `
				<div class="table-responsive">
					<table class="okr-table">
						<thead><tr>
							<th>${__('Objective Title')}</th>
							<th>${__('Objective ID')}</th>
							<th>${__('Owner User')}</th>
							<th>${__('Reviewer')}</th>
							<th>${__('Self Rating')}</th>
							<th>${__('Manager Rating')}</th>
							<th>${__('Overall Rating')}</th>
							<th>${__('Rating Gap')}</th>
							<th>${__('Decision')}</th>
							<th>${__('Review Status')}</th>
							<th>${__('Review Date')}</th>
							<th>${__('Manager Feedback')}</th>
							<th>${__('Recommended Action')}</th>
						</tr></thead>
						<tbody>${rows.map(row => `<tr style="${row.has_issue ? 'background:#fff7ed;' : ''}">
							<td><a href="${frappe.utils.get_form_link('OKR Objective', row.objective || '')}" style="font-weight:500;">${this.esc(row.objective_title || row.objective)}</a></td>
							<td><small class="text-muted">${this.esc(row.objective || '')}</small></td>
							<td>${this.esc(row.owner || '—')}</td>
							<td>${this.esc(row.reviewer || '—')}</td>
							<td>${this.esc(row.self_rating_display || '—')}</td>
							<td>${this.esc(row.manager_rating_display || '—')}</td>
							<td>${this.esc(row.overall_rating_display || '—')}</td>
							<td>${this.esc(row.rating_gap || 0)}</td>
							<td>${this.esc(row.decision || '—')}</td>
							<td>${this.esc(row.review_status || '—')}</td>
							<td>${this.esc(row.review_date || '—')}</td>
							<td style="max-width:220px;font-size:12px;">${this.esc(row.manager_feedback || '—')}</td>
							<td style="max-width:220px;font-size:12px;">${this.esc(row.recommended_action || '')}</td>
						</tr>`).join('')}</tbody>
					</table>
				</div>` : `<div class="okr-empty-state"><div class="okr-empty-icon">✓</div>${__('No review ratings found yet.')}</div>`}
			</div>`;
	}

	recordRoute(row) {
		const doctypeMap = {
			'Objective': 'OKR Objective',
			'Key Result': 'OKR Key Result',
		};
		const doctype = doctypeMap[row.type] || row.type || '';
		return frappe.utils.get_form_link(doctype, row.record || '');
	}
}
