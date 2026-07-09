frappe.pages['admin-workspace'].on_page_load = function(wrapper) {
        new OKRAdminWorkspace(wrapper);
};

class OKRAdminWorkspace {
        constructor(wrapper) {
                this.wrapper = wrapper;
                this.page = frappe.ui.make_app_page({ parent: wrapper, title: __('Admin Workspace'), single_column: true });
                this.body = jQuery('<div class="okr-admin-page"></div>').appendTo(this.page.main);
                this.filters = { year: '', quarter: '', sprint: '', department: '', owner: '', status: '' };
                this.options = {};
                this.data = null;
                this.render_shell();
                this.bind_events();
                this.load_options();
        }

        render_shell() {
                this.body.html(`
                        <div class="okr-admin-shell">
                                <section class="okr-admin-hero">
                                        <div>
                                                <span class="okr-admin-eyebrow">${__('Leadership Dashboard')}</span>
                                                <h1>${__('Executive OKR Dashboard')}</h1>
                                                <p>${__('Organization health, department performance, risk, activity, and execution signals from current OKR records.')}</p>
                                        </div>
                                        <div class="okr-admin-refresh">
                                                <span>${__('Last updated')}</span>
                                                <strong data-updated-at>${__('Loading')}</strong>
                                                <button class="btn btn-sm btn-default" data-refresh>${__('Refresh')}</button>
                                        </div>
                                </section>

                                <section class="okr-admin-section okr-filter-section">
                                        <div class="okr-admin-section-head compact">
                                                <div><span>${__('Quick Filters')}</span><h2>${__('Leadership view')}</h2></div>
                                                <button class="btn btn-sm btn-default" data-clear-filters>${__('Clear')}</button>
                                        </div>
                                        <div class="okr-admin-filters" data-filter-bar></div>
                                </section>

                                <section class="okr-admin-section">
                                        <div class="okr-admin-section-head compact">
                                                <div><span>${__('Organization Overview')}</span><h2>${__('Live OKR metrics')}</h2></div>
                                        </div>
                                        <div class="okr-admin-metric-grid" data-metrics></div>
                                </section>

                                <section class="okr-admin-section">
                                        <div class="okr-admin-section-head compact">
                                                <div><span>${__('Charts')}</span><h2>${__('Execution trends')}</h2></div>
                                        </div>
                                        <div class="okr-admin-chart-grid" data-charts></div>
                                </section>

                                <section class="okr-admin-grid two-col wide-left">
                                        <div class="okr-admin-panel">
                                                <div class="okr-admin-panel-head"><span>${__('Department Performance')}</span><h3>${__('Progress by department')}</h3></div>
                                                <div data-department-performance></div>
                                        </div>
                                        <div class="okr-admin-panel">
                                                <div class="okr-admin-panel-head"><span>${__('Quick Actions')}</span><h3>${__('Available actions')}</h3></div>
                                                ${this.quick_actions()}
                                        </div>
                                </section>

                                <section class="okr-admin-grid two-col">
                                        <div class="okr-admin-panel">
                                                <div class="okr-admin-panel-head"><span>${__('At Risk Dashboard')}</span><h3>${__('Items needing attention')}</h3></div>
                                                <div data-risk></div>
                                        </div>
                                        <div class="okr-admin-panel">
                                                <div class="okr-admin-panel-head"><span>${__('Latest Activity')}</span><h3>${__('Newest OKR updates')}</h3></div>
                                                <div data-activity></div>
                                        </div>
                                </section>

                                <section class="okr-admin-section">
                                        <div class="okr-admin-section-head compact">
                                                <div><span>${__('Top Performers')}</span><h2>${__('Check-in based contribution')}</h2></div>
                                        </div>
                                        <div data-top-performers></div>
                                </section>
                        </div>
                `);
        }

        bind_events() {
                this.body.on('change', '[data-filter]', (event) => {
                        const field = event.currentTarget.getAttribute('data-filter');
                        this.filters[field] = event.currentTarget.value || '';
                        if (field === 'year' || field === 'quarter') this.render_filters();
                        this.load();
                });
                this.body.on('click', '[data-clear-filters]', () => {
                        this.filters = { year: '', quarter: '', sprint: '', department: '', owner: '', status: '' };
                        this.render_filters();
                        this.load();
                });
                this.body.on('click', '[data-refresh]', () => this.load());
                this.body.on('click', '[data-open-doc]', (event) => {
                        const target = event.currentTarget;
                        frappe.set_route('Form', target.getAttribute('data-doctype'), target.getAttribute('data-name'));
                });
                this.body.on('click', '[data-department]', (event) => {
                        const department = event.currentTarget.getAttribute('data-department');
                        this.open_list('OKR Objective', department === 'Unassigned' ? {} : { department });
                });
                this.body.on('click', '[data-action]', (event) => this.handle_action(event.currentTarget.getAttribute('data-action'), event));
        }

        load_options() {
                frappe.call({
                        method: 'okr_management.okr_management.page.admin_workspace.admin_workspace.get_filter_options',
                        callback: (r) => {
                                this.options = r.message || {};
                                this.render_filters();
                                this.load();
                        }
                });
        }

        load() {
                this.body.addClass('loading');
                frappe.call({
                        method: 'okr_management.okr_management.page.admin_workspace.admin_workspace.get_dashboard_data',
                        args: this.filters,
                        freeze: true,
                        freeze_message: __('Loading Executive OKR Dashboard...'),
                        callback: (r) => {
                                this.data = r.message || {};
                                this.render_dashboard();
                        },
                        error: () => {
                                frappe.show_alert({ message: __('Unable to load OKR dashboard data.'), indicator: 'red' });
                        },
                        always: () => this.body.removeClass('loading')
                });
        }

        render_filters() {
                const sprints = (this.options.sprints || []).filter(sprint => {
                        if (this.filters.year && sprint.financial_year !== this.filters.year) return false;
                        if (this.filters.quarter && sprint.financial_quarter !== this.filters.quarter) return false;
                        return true;
                });
                this.body.find('[data-filter-bar]').html(`
                        ${this.filter_select('year', __('Year'), this.options.years || [], 'name', 'name')}
                        ${this.filter_select('quarter', __('Quarter'), (this.options.quarters || []).map(v => ({ name: v })), 'name', 'name')}
                        ${this.filter_select('sprint', __('Sprint'), sprints, 'name', 'sprint_name')}
                        ${this.filter_select('department', __('Department'), this.options.departments || [], 'name', 'department_name')}
                        ${this.filter_select('owner', __('Owner'), this.options.owners || [], 'name', 'full_name')}
                        ${this.filter_select('status', __('Status'), (this.options.statuses || []).map(v => ({ name: v })), 'name', 'name')}
                `);
        }

        filter_select(field, label, rows, value_field, label_field) {
                const selected = this.filters[field] || '';
                const options = [`<option value="">${__('All')}</option>`].concat((rows || []).map(row => {
                        const value = row[value_field] || '';
                        const text = row[label_field] || value;
                        return `<option value="${this.e(value)}" ${selected === value ? 'selected' : ''}>${this.e(text)}</option>`;
                }));
                return `<label class="okr-admin-filter"><span>${label}</span><select class="form-control" data-filter="${field}">${options.join('')}</select></label>`;
        }

        render_dashboard() {
                this.body.find('[data-updated-at]').text(this.data.updated_at || __('Loaded'));
                this.render_metrics();
                this.render_charts();
                this.render_department_performance();
                this.render_risk();
                this.render_activity();
                this.render_top_performers();
        }

        render_metrics() {
                const m = this.data.metrics || {};
                const cards = [
                        ['Total OKR Plans', m.total_plans, 'neutral', 'OKR Plan'],
                        ['Active OKR Plans', m.active_plans, 'blue', 'OKR Plan', { status: 'Active' }],
                        ['Active Sprints', m.active_sprints, 'blue', 'OKR Sprint', { status: 'Active' }],
                        ['Total Objectives', m.total_objectives, 'green', 'OKR Objective'],
                        ['Total Key Results', m.total_key_results, 'purple', 'OKR Key Result'],
                        ['Total Action Items', m.total_action_items, 'purple', 'OKR Action Item'],
                        ['Total Check-ins', m.total_checkins, 'green', 'OKR Check In'],
                        ['Organization Progress %', this.percent(m.organization_progress), 'neutral', 'OKR Objective'],
                        ['Completed Objectives', m.completed_objectives, 'green', 'OKR Objective', { status: 'Completed' }],
                        ['At Risk Objectives', m.at_risk_objectives, 'red', 'OKR Objective'],
                        ['Blocked Action Items', m.blocked_action_items, 'red', 'OKR Action Item', { status: 'Blocked' }],
                        ['Overdue Action Items', m.overdue_action_items, 'red', 'OKR Action Item']
                ];
                this.body.find('[data-metrics]').html(cards.map(card => this.metric_card(card)).join(''));
        }

        metric_card(card) {
                const [label, value, tone, doctype, extra_filters] = card;
                return `
                        <button class="okr-admin-metric ${tone}" data-action="open-list" data-doctype="${doctype}" data-filters='${this.e(JSON.stringify(extra_filters || {}))}'>
                                <span>${__(label)}</span>
                                <strong>${this.e(value == null ? 0 : value)}</strong>
                        </button>
                `;
        }

        render_charts() {
                const charts = this.data.charts || {};
                const html = [
                        this.bar_chart(__('Progress by Department'), charts.progress_by_department || [], '%'),
                        this.bar_chart(__('Objective Status Distribution'), charts.objective_status_distribution || [], ''),
                        this.bar_chart(__('Monthly Check-ins'), charts.monthly_checkins || [], ''),
                        this.bar_chart(__('Sprint Completion Trend'), charts.sprint_completion_trend || [], ''),
                        this.bar_chart(__('Confidence Distribution'), charts.confidence_distribution || [], '')
                ].join('');
                this.body.find('[data-charts]').html(html);
        }

        bar_chart(title, rows, suffix) {
                const max = Math.max(1, ...rows.map(row => flt(row.value)));
                const body = rows.length ? rows.map(row => {
                        const value = flt(row.value, 2);
                        const width = Math.max(2, Math.min(100, value / max * 100));
                        return `
                                <div class="okr-chart-row">
                                        <div><span>${this.e(row.label)}</span><strong>${this.e(value)}${suffix}</strong></div>
                                        <i><b style="width:${width}%"></b></i>
                                </div>
                        `;
                }).join('') : this.empty_state(__('No matching records'));
                return `<div class="okr-admin-chart-card"><h3>${title}</h3>${body}</div>`;
        }

        render_department_performance() {
                const rows = this.data.department_performance || [];
                if (!rows.length) {
                        this.body.find('[data-department-performance]').html(this.empty_state(__('No departments found')));
                        return;
                }
                this.body.find('[data-department-performance]').html(`
                        <div class="okr-admin-table-wrap"><table class="okr-admin-table clickable">
                                <thead><tr><th>${__('Department')}</th><th>${__('Progress %')}</th><th>${__('Objectives')}</th><th>${__('Key Results')}</th><th>${__('Confidence')}</th><th>${__('Status')}</th></tr></thead>
                                <tbody>${rows.map(row => `
                                        <tr data-department="${this.e(row.department)}">
                                                <td><strong>${this.e(row.department)}</strong></td>
                                                <td>${this.percent(row.progress)}</td>
                                                <td>${this.e(row.objectives)}</td>
                                                <td>${this.e(row.key_results)}</td>
                                                <td>${this.e(row.confidence || '')}</td>
                                                <td><span class="okr-admin-badge ${this.status_class(row.status)}">${this.e(row.status)}</span></td>
                                        </tr>
                                `).join('')}</tbody>
                        </table></div>
                `);
        }

        render_risk() {
                const rows = this.data.at_risk || [];
                if (!rows.length) {
                        this.body.find('[data-risk]').html(this.empty_state(__('No risk items match the current filters')));
                        return;
                }
                this.body.find('[data-risk]').html(`<div class="okr-admin-list dense">${rows.map(row => `
                        <button class="okr-admin-risk ${this.e(row.severity)}" data-open-doc data-doctype="${this.e(row.doctype)}" data-name="${this.e(row.name)}">
                                <span>${this.e(row.type)}</span>
                                <strong>${this.e(row.title)}</strong>
                                <small>${this.e([row.department, row.owner, row.detail].filter(Boolean).join(' | '))}</small>
                        </button>
                `).join('')}</div>`);
        }

        render_activity() {
                const rows = this.data.latest_activity || [];
                if (!rows.length) {
                        this.body.find('[data-activity]').html(this.empty_state(__('No activity matches the current filters')));
                        return;
                }
                this.body.find('[data-activity]').html(`<div class="okr-admin-list">${rows.map(row => `
                        <button class="okr-admin-list-item" data-open-doc data-doctype="${this.e(row.doctype)}" data-name="${this.e(row.name)}">
                                <span></span>
                                <div><strong>${this.e(row.type)}</strong><p>${this.e(row.title)}</p><small>${this.e([row.owner, row.when].filter(Boolean).join(' | '))}</small></div>
                        </button>
                `).join('')}</div>`);
        }

        render_top_performers() {
                const rows = this.data.top_performers || [];
                if (!rows.length) {
                        this.body.find('[data-top-performers]').html(this.empty_state(__('No check-in based performer data found')));
                        return;
                }
                this.body.find('[data-top-performers]').html(`
                        <div class="okr-admin-table-wrap"><table class="okr-admin-table">
                                <thead><tr><th>${__('Employee')}</th><th>${__('Department')}</th><th>${__('Completed Objectives')}</th><th>${__('Average Progress')}</th><th>${__('Confidence')}</th></tr></thead>
                                <tbody>${rows.map(row => `
                                        <tr>
                                                <td><strong>${this.e(row.employee_name || row.employee)}</strong><small>${this.e(row.employee)}</small></td>
                                                <td>${this.e(row.department || '')}</td>
                                                <td>${this.e(row.completed_objectives)}</td>
                                                <td>${this.percent(row.average_progress)}</td>
                                                <td>${this.e(row.confidence || '')}</td>
                                        </tr>
                                `).join('')}</tbody>
                        </table></div>
                `);
        }

        quick_actions() {
                return `<div class="okr-admin-actions">
                        <button class="btn btn-primary" data-action="new-plan">+ ${__('Create OKR Plan')}</button>
                        <button class="btn btn-default" data-action="new-sprint">+ ${__('Create Sprint')}</button>
                        <button class="btn btn-default" data-action="new-objective">+ ${__('Create Objective')}</button>
                        <button class="btn btn-default" data-action="new-key-result">+ ${__('Create Key Result')}</button>
                        <button class="btn btn-default" data-action="open-reports">${__('Open Reports')}</button>
                </div>`;
        }

        handle_action(action, event) {
                if (action === 'new-plan') return frappe.new_doc('OKR Plan');
                if (action === 'new-sprint') return frappe.new_doc('OKR Sprint');
                if (action === 'new-objective') return frappe.new_doc('OKR Objective');
                if (action === 'new-key-result') return frappe.new_doc('OKR Key Result');
                if (action === 'open-reports') return frappe.set_route('List', 'OKR Objective', 'Report');
                if (action === 'open-list') {
                        const target = event.currentTarget;
                        const doctype = target.getAttribute('data-doctype');
                        const filters = JSON.parse(target.getAttribute('data-filters') || '{}');
                        return this.open_list(doctype, filters);
                }
        }

        open_list(doctype, extra_filters) {
                const filters = Object.assign({}, extra_filters || {});
                if (this.filters.year && doctype !== 'User') filters.financial_year = this.filters.year;
                if (this.filters.department && doctype !== 'User') filters.department = this.filters.department;
                if (this.filters.owner) {
                        filters[doctype === 'OKR Check In' ? 'reported_by' : doctype === 'OKR Sprint' ? 'sprint_owner' : 'owner_user'] = this.filters.owner;
                }
                if (this.filters.status) filters.status = this.filters.status;
                frappe.set_route('List', doctype, filters);
        }

        empty_state(message) {
                return `<div class="okr-admin-empty">${this.e(message)}</div>`;
        }

        status_class(status) {
                return frappe.scrub(status || '').replace(/_/g, '-');
        }

        percent(value) {
                return `${flt(value || 0, 1)}%`;
        }

        e(value) {
                return frappe.utils.escape_html(String(value == null ? '' : value));
        }
}
