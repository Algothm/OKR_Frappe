frappe.pages['admin-workspace'].on_page_load = function(wrapper) {
        new OKRAdminWorkspace(wrapper);
};

class OKRAdminWorkspace {
        constructor(wrapper) {
                this.wrapper = wrapper;
                this.page = frappe.ui.make_app_page({ parent: wrapper, title: __('OKR Command'), single_column: true });
                jQuery(this.wrapper).find('.page-head').hide();
                this.body = jQuery('<div class="okr-admin-page"></div>').appendTo(this.page.main);

                this.filters = { year: '', plan: '', department: '', status: '' };
                this.options = {};
                this.data = null;

                this.current_view = 'dashboard'; // 'dashboard' | 'detail'
                this.selected_objective = null;
                this.filter_drawer_open = true;
                this._active_card_filter = null;

                this.init_shell();
                this.bind_events();
                this.load_options();
        }

        init_shell() {
                this.body.html(`
                        <div class="okr-cmd-shell">

                                <!-- Dynamic View Container (Dashboard vs Detail) -->
                                <div data-view-container></div>
                        </div>
                `);
        }

        bind_events() {
                // Filter bar toggle & actions
                this.body.on('click', '[data-toggle-filters]', (e) => {
                        if ($(e.target).closest('[data-clear-filters]').length) return;
                        this.toggle_filter_drawer();
                });
                this.body.on('click', '[data-clear-filters]', (e) => {
                        e.stopPropagation();
                        this.filters = { year: '', plan: '', department: '', status: '' };
                        this.render_filters();
                        this.render_filter_summary();
                        this._reset_card_filter();
                        this.load();
                });
                this.body.on('change', '[data-filter]', (e) => {
                        const field = e.currentTarget.getAttribute('data-filter');
                        this.filters[field] = e.currentTarget.value || '';
                        if (field === 'year') this.render_filters();
                        this.render_filter_summary();
                        this._reset_card_filter();
                        this.load();
                });

                // Refresh trigger
                this.body.on('click', '[data-refresh]', () => this.load());
                this.body.on('click', '[data-select-plan]', (e) => this.select_plan($(e.currentTarget).data('select-plan')));
                this.body.on('click', '[data-plan-toggle]', (e) => {
                        e.preventDefault();
                        $(e.currentTarget).closest('.okr-plan-tree-card').toggleClass('expanded');
                });
                this.body.on('click', '[data-objective-toggle]', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        $(e.currentTarget).closest('.okr-plan-objective').toggleClass('expanded');
                });
                this.body.on('click', '[data-summary-card]', (e) => this._handle_summary_card_click($(e.currentTarget).data('summary-card')));
                this.body.on('click', '[data-clear-plan]', (e) => { e.preventDefault(); this.clear_plan(); });

                // Navigation between Dashboard and Detail views
                this.body.on('click', '[data-action="back-to-dashboard"]', (e) => {
                        e.preventDefault();
                        this.current_view = 'dashboard';
                        this.selected_objective = null;
                        this.render_current_view();
                });

                // Click objective row to open Detail view
                this.body.on('click', '[data-objective-row]', (e) => {
                        const index = $(e.currentTarget).data('objective-index');
                        const rows = this.data.attention_required || [];
                        const row = rows[index] || rows[0];
                        if (row) {
                                this.open_objective_detail(row);
                        }
                });

                this.body.on('click', '.okr-clear-card-filter', (e) => {
                        e.preventDefault();
                        this._reset_card_filter();
                });

                // Key Result card expansion toggle
                this.body.on('click', '[data-kr-toggle]', (e) => {
                        const card = $(e.currentTarget).closest('.okr-kr-card');
                        card.toggleClass('expanded');
                });

                // Check-in trail expansion toggle inside initiative
                this.body.on('click', '[data-toggle-trail]', (e) => {
                        e.stopPropagation();
                        const row = $(e.currentTarget).closest('.okr-init-row');
                        row.toggleClass('trail-open');
                        const isOpen = row.hasClass('trail-open');
                        const count = $(e.currentTarget).data('count') || 3;
                        $(e.currentTarget).html(`${isOpen ? '▾' : '▸'} ${count} check-ins — ${isOpen ? 'hide trail' : 'view trail'}`);
                });
        }

        _handle_summary_card_click(card_type) {
                const scroll_to = (selector) => {
                        const el = this.body.find(selector)[0];
                        if (el) {
                                el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        }
                };

                // If clicking the already active card, reset the card filters
                if (this._active_card_filter === card_type) {
                        this._reset_card_filter();
                        return;
                }

                this._active_card_filter = card_type;

                // Mark active card for visual feedback
                this.body.find('[data-summary-card]').removeClass('okr-card-active');
                this.body.find(`[data-summary-card="${card_type}"]`).addClass('okr-card-active');
                this.body.find('.okr-clear-card-filter').show();

                if (card_type === 'needs_attention') {
                        // Hide OKR Plans section completely
                        this.body.find('#okr-plans-section').hide();
                        this.body.find('.okr-plan-grid').hide();
                        // Show Needs Attention list and show all attention rows
                        this.body.find('#okr-needs-attention-section').show();
                        this.body.find('.okr-attention-card').show();
                        this.body.find('.okr-attention-row').show();
                        scroll_to('#okr-needs-attention-section');

                } else if (card_type === 'plans' || card_type === 'objectives' || card_type === 'overall_progress') {
                        // Show everything, scroll to plans section
                        this.body.find('#okr-plans-section').show();
                        this.body.find('.okr-plan-grid').show();
                        this.body.find('#okr-needs-attention-section').show();
                        this.body.find('.okr-attention-card').show();
                        this.body.find('.okr-attention-row').show();
                        this.body.find('.okr-plan-card').show();
                        scroll_to('#okr-plans-section');

                } else if (card_type === 'blocked') {
                        // Show plans section
                        this.body.find('#okr-plans-section').show();
                        this.body.find('.okr-plan-grid').show();
                        // Show Needs Attention section
                        this.body.find('#okr-needs-attention-section').show();
                        this.body.find('.okr-attention-card').show();

                        // Filter attention rows: show only rows where reason contains 'Blocked'
                        const attn_rows = this.body.find('.okr-attention-row');
                        attn_rows.each((i, el) => {
                                const pill = $(el).find('.okr-status-pill').text().trim().toLowerCase();
                                const title = $(el).find('.okr-attention-row__title strong').text().trim().toLowerCase();
                                $(el).toggle(pill.includes('block') || title.includes('block'));
                        });
                        // Filter plan cards: show only plans with blocked > 0
                        const all_plans = this.data.plan_summaries || [];
                        this.body.find('.okr-plan-card').each((i, el) => {
                                const plan_name = $(el).data('plan-name');
                                const plan = all_plans.find(p => p.name === plan_name);
                                const blocked = plan ? cint(plan.blocked_objectives || plan.blocked || 0) : 0;
                                $(el).toggle(blocked > 0);
                        });
                        scroll_to('#okr-plans-section');
                        frappe.show_alert({ message: __('Showing only Blocked items'), indicator: 'orange' });

                } else if (card_type === 'achieved') {
                        // Show plans section
                        this.body.find('#okr-plans-section').show();
                        this.body.find('.okr-plan-grid').show();
                        // Filter attention rows: hide — achieved items won't be in attention list
                        this.body.find('#okr-needs-attention-section').hide();
                        this.body.find('.okr-attention-card').hide();
                        this.body.find('.okr-attention-row').hide();
                        // Filter plan cards: show only plans with progress >= 100 or status Completed
                        const all_plans = this.data.plan_summaries || [];
                        this.body.find('.okr-plan-card').each((i, el) => {
                                const plan_name = $(el).data('plan-name');
                                const plan = all_plans.find(p => p.name === plan_name);
                                const progress = plan ? flt(plan.progress || 0) : 0;
                                const status = plan ? (plan.status || '') : '';
                                $(el).toggle(progress >= 100 || status === 'Completed');
                        });
                        scroll_to('#okr-plans-section');
                        frappe.show_alert({ message: __('Showing only Achieved plans'), indicator: 'green' });
                }
        }

        _reset_card_filter() {
                this._active_card_filter = null;
                this.body.find('[data-summary-card]').removeClass('okr-card-active');
                this.body.find('.okr-clear-card-filter').hide();
                this.body.find('#okr-plans-section').show();
                this.body.find('.okr-plan-grid').show();
                this.body.find('#okr-needs-attention-section').show();
                this.body.find('.okr-attention-card').show();
                this.body.find('.okr-attention-row').show();
                this.body.find('.okr-plan-card').show();
        }

        load_options() {
                frappe.call({
                        method: 'okr_management.okr_management.page.admin_workspace.admin_workspace.get_filter_options',
                        callback: (r) => {
                                this.options = r.message || {};
                                this.load();
                        }
                });
        }

        load() {
                this.body.addClass('loading');
                frappe.call({
                        method: 'okr_management.okr_management.page.admin_workspace.admin_workspace.get_dashboard_data',
                        args: { ...this.filters, owner: '' },
                        freeze: true,
                        freeze_message: __('Syncing Operational Control Room...'),
                        callback: (r) => {
                                this.data = r.message || {};
                                this.render_current_view();
                        },
                        error: () => frappe.show_alert({ message: __('Unable to load OKR command data.'), indicator: 'red' }),
                        always: () => this.body.removeClass('loading')
                });
        }


        render_current_view() {
                this.update_breadcrumb();
                const container = this.body.find('[data-view-container]');

                if (this.current_view === 'detail' && this.selected_objective) {
                        container.html(this.render_detail_html(this.selected_objective));
                } else {
                        container.html(this.render_dashboard_html());
                        this.render_filters();
                        this.render_filter_summary();

                        if (this._active_card_filter) {
                                const card_type = this._active_card_filter;
                                this.body.find('[data-summary-card]').removeClass('okr-card-active');
                                this.body.find(`[data-summary-card="${card_type}"]`).addClass('okr-card-active');
                                this.body.find('.okr-clear-card-filter').show();

                                if (card_type === 'needs_attention') {
                                        this.body.find('#okr-plans-section').hide();
                                        this.body.find('.okr-plan-grid').hide();
                                        this.body.find('#okr-needs-attention-section').show();
                                        this.body.find('.okr-attention-card').show();
                                        this.body.find('.okr-attention-row').show();
                                } else if (card_type === 'blocked') {
                                        this.body.find('#okr-plans-section').show();
                                        this.body.find('.okr-plan-grid').show();
                                        this.body.find('#okr-needs-attention-section').show();
                                        this.body.find('.okr-attention-card').show();

                                        const attn_rows = this.body.find('.okr-attention-row');
                                        attn_rows.each((i, el) => {
                                                const pill = $(el).find('.okr-status-pill').text().trim().toLowerCase();
                                                const title = $(el).find('.okr-attention-row__title strong').text().trim().toLowerCase();
                                                $(el).toggle(pill.includes('block') || title.includes('block'));
                                        });
                                        const all_plans = this.data.plan_summaries || [];
                                        this.body.find('.okr-plan-card').each((i, el) => {
                                                const plan_name = $(el).data('plan-name');
                                                const plan = all_plans.find(p => p.name === plan_name);
                                                const blocked = plan ? cint(plan.blocked_objectives || plan.blocked || 0) : 0;
                                                $(el).toggle(blocked > 0);
                                        });
                                } else if (card_type === 'achieved') {
                                        this.body.find('#okr-plans-section').show();
                                        this.body.find('.okr-plan-grid').show();
                                        this.body.find('#okr-needs-attention-section').hide();
                                        this.body.find('.okr-attention-card').hide();
                                        this.body.find('.okr-attention-row').hide();

                                        const all_plans = this.data.plan_summaries || [];
                                        this.body.find('.okr-plan-card').each((i, el) => {
                                                const plan_name = $(el).data('plan-name');
                                                const plan = all_plans.find(p => p.name === plan_name);
                                                const progress = plan ? flt(plan.progress || 0) : 0;
                                                const status = plan ? (plan.status || '') : '';
                                                $(el).toggle(progress >= 100 || status === 'Completed');
                                        });
                                } else {
                                        this.body.find('#okr-plans-section').show();
                                        this.body.find('.okr-plan-grid').show();
                                        this.body.find('#okr-needs-attention-section').show();
                                        this.body.find('.okr-attention-card').show();
                                        this.body.find('.okr-attention-row').show();
                                        this.body.find('.okr-plan-card').show();
                                }
                        }
                }
        }

        update_breadcrumb() {
                const bc = this.body.find('[data-breadcrumb]');
                if (this.current_view === 'detail' && this.selected_objective) {
                        bc.html(`<span>/</span> <a data-action="back-to-dashboard">Admin workspace</a> <span>/</span> <strong>${this.e(this.selected_objective.objective)}</strong>`);
                } else {
                        bc.html(`<span>/</span> <a data-action="back-to-dashboard">Admin workspace</a>`);
                }
        }

        /* ==========================================================================
           DASHBOARD VIEW RENDER
           ========================================================================== */
        render_dashboard_html() {
                const m = this.data.metrics || {};
                const updated = this.format_admin_datetime(this.data.updated_at || new Date());
                const rows = this.data.attention_required || [];
                const plans = this.data.plan_summaries || [];
                const objectives = plans.reduce((n, row) => n + cint(row.objectives || 0), 0);
                return `
                        <section class="okr-filter-card open">
                          <div class="okr-filter-card__header" data-toggle-filters>
                            <div class="okr-filter-card__summary"><span data-filter-summary-text>${this.get_filter_summary_text()}</span><span class="okr-chevron"></span></div>
                            <button class="okr-btn-clear" data-clear-filters>Clear</button>
                          </div>
                          <div class="okr-filter-grid" data-filter-bar></div>
                        </section>
                        ${this.render_selected_plan_chip(plans)}
                        <div class="okr-section-head">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                        <h2 class="okr-section-title" style="margin: 0;">Summary</h2>
                                        <button class="btn btn-xs btn-default okr-clear-card-filter" style="display: none; padding: 2px 8px; font-size: 11px; font-weight: 500;">Clear Card Filter</button>
                                </div>
                                ${this.render_progress_legend()}
                        </div>
                        <section class="okr-health-strip">
                          <button class="okr-health-strip__metric-col" data-summary-card="needs_attention" title="Click to scroll to Needs Attention">
                                <span class="okr-metric-num okr-metric-num--${(this.data.attention_count||0)>0?'critical':'good'}">${cint(this.data.attention_count||0)}</span>
                                <span class="okr-metric-label">Needs Attention</span>
                          </button>
                          <button class="okr-health-strip__metric-col" data-summary-card="plans" title="Click to scroll to OKR Plans">
                                <span class="okr-metric-num">${plans.length}</span>
                                <span class="okr-metric-label">Plans</span>
                          </button>
                          <button class="okr-health-strip__metric-col" data-summary-card="objectives" title="Click to scroll to OKR Plans">
                                <span class="okr-metric-num">${objectives}</span>
                                <span class="okr-metric-label">Objectives</span>
                          </button>
                          <button class="okr-health-strip__metric-col" data-summary-card="overall_progress" title="Overall progress">
                                <span class="okr-metric-num okr-metric-num--${this.progress_severity(m.company_progress)}">${this.percent(m.company_progress)}</span>
                                <span class="okr-metric-label">Overall Progress</span>
                          </button>
                          <button class="okr-health-strip__metric-col" data-summary-card="blocked" title="Click to filter blocked objectives">
                                <span class="okr-metric-num okr-metric-num--${(m.blocked_objectives||0)>0?'critical':'good'}">${cint(m.blocked_objectives||0)}</span>
                                <span class="okr-metric-label">Blocked Objectives</span>
                          </button>
                          <button class="okr-health-strip__metric-col" data-summary-card="achieved" title="Click to filter achieved objectives">
                                <span class="okr-metric-num okr-metric-num--good">${cint(m.achieved_objectives||0)}</span>
                                <span class="okr-metric-label">Achieved Objectives</span>
                          </button>
                        </section>
                        ${this.render_plan_section(plans)}
                        <div class="okr-section-head" id="okr-needs-attention-section"><h2 class="okr-section-title">Needs Attention</h2><span class="okr-section-hint">Blocked, on hold, missing check-in, or low progress</span></div>
                        <section class="okr-attention-card">
                          ${rows.length ? rows.map((row,idx)=>`<button class="okr-attention-row" data-objective-row data-objective-index="${idx}"><span class="okr-dept-tag">${this.e(row.department||'GENERAL')}</span><div class="okr-attention-row__title"><strong>${this.e(row.objective)}</strong><span>${this.e(row.owner||'unassigned')}</span></div><div class="okr-progress-bar"><div class="okr-progress-bar__fill okr-progress-bar__fill--${this.progress_severity(row.progress)}" style="width:${this.progress_width(row.progress)}%"></div></div><span class="okr-attention-row__pct">${this.percent(row.progress)}</span><span class="okr-status-pill okr-status-pill--${this.status_slug(row.reason)}">${this.e(row.reason||'Needs attention')}</span><span class="okr-row-arrow">&gt;</span></button>`).join('') : `<div style="padding:32px;text-align:center;color:var(--muted)">No items need attention right now.</div>`}
                        </section>
                `;
        }

        render_selected_plan_chip(planRows) {
                if (!this.filters.plan) return '';
                const selected = (planRows || []).find(row => row.name === this.filters.plan);
                const label = selected ? (selected.plan_name || selected.name) : this.filters.plan;
                return `
                        <div class="okr-plan-scope-chip">
                                <span>Viewing Plan:</span>
                                <strong>${this.e(label)}</strong>
                                <button type="button" data-clear-plan>Clear</button>
                        </div>
                `;
        }

        render_plan_section(rows) {
                return `
                        <!-- OKR Plans -->
                        <div class="okr-section-head" id="okr-plans-section">
                                <h2 class="okr-section-title">OKR Plans</h2>
                                <span class="okr-section-hint">plan overview</span>
                        </div>
                        <section class="okr-plan-grid">
                                ${rows.length ? rows.map(row => this.render_plan_card(row)).join('') : `<div class="okr-plan-empty">No active OKR plans found for the current filters.</div>`}
                        </section>
                `;
        }

        render_plan_card(row) {
                const active = this.filters.plan === row.name;
                const blocked = cint(row.blocked_objectives || row.blocked || 0);

                // New simplified color logic: Red if blocked, Yellow if 0-50%, Green if >50%
                let progress_class = 'good';
                if (blocked > 0) {
                        progress_class = 'critical';
                } else if (flt(row.progress) <= 50) {
                        progress_class = 'warning';
                }

                const freq = this.e(row.sprint_frequency || '');
                const obj_count = cint(row.objectives || 0);

                return `
                        <div class="okr-plan-tree-card ${active ? 'active expanded' : ''}"><button type="button" class="okr-plan-card ${active ? 'active' : ''}" data-plan-toggle data-plan-name="${this.e(row.name)}">
                                <div class="okr-plan-card__head">
                                        <div>
                                                <strong>${this.e(row.plan_name || row.name)}</strong>
                                                <span>${this.e(row.name || '')}</span>
                                                <div class="okr-plan-card__meta-inline">
                                                        ${freq ? `<span class="okr-plan-freq-pill">${freq}</span>` : ''}
                                                        <span class="okr-plan-meta-stats">${obj_count} Objective${obj_count !== 1 ? 's' : ''} · <span class="${blocked > 0 ? 'okr-plan-critical-text' : ''}">${blocked} Blocked</span></span>
                                                </div>
                                        </div>
                                        <span class="okr-chevron"></span><span class="okr-status-pill okr-status-pill--${this.status_slug(row.status)}">${this.e(row.status || 'Draft')}</span>
                                </div>
                                <div class="okr-plan-progress">
                                        <div>
                                                <span>Progress</span>
                                                <strong class="okr-metric-num okr-metric-num--${progress_class}">${this.percent(row.progress)}</strong>
                                        </div>
                                        <div class="okr-progress-bar">
                                                <div class="okr-progress-bar__fill okr-progress-bar__fill--${progress_class}" style="width: ${this.progress_width(row.progress)}%;"></div>
                                        </div>
                                </div>
                        </button><div class="okr-plan-tree-body">${this.render_plan_tree(row)}</div></div>
                `;
        }

        render_plan_tree(plan) {
                const rows = plan.objective_tree || [];
                if (!rows.length) return '<div class="okr-plan-tree-empty">' + __('No objectives in this plan.') + '</div>';
                return rows.map((obj, i) => {
                        const krs = obj.key_results || [];
                        const actions = krs.reduce((n, kr) => n + (kr.action_items || []).length, 0);
                        return '<section class="okr-plan-objective ' + (i === 0 ? 'expanded' : '') + '"><button class="okr-plan-objective__header" data-objective-toggle>' +
                                '<span class="okr-objective-badge">O</span><span class="okr-plan-objective__title"><strong>' + this.e(obj.title) + '</strong><small>' +
                                this.pluralize(krs.length, 'Key Result') + ' &middot; ' + this.pluralize(actions, 'Action Item') + '</small></span><b>' + this.percent(obj.progress) +
                                '</b><span class="okr-status-pill okr-status-pill--' + this.status_slug(obj.status) + '">' + this.e(obj.status || 'Draft') +
                                '</span><span class="okr-chevron"></span></button><div class="okr-plan-objective__body">' +
                                (krs.length ? krs.map(kr => this.render_plan_kr(kr)).join('') : '<div class="okr-plan-tree-empty">' + __('No key results.') + '</div>') + '</div></section>';
                }).join('');
        }

        render_plan_kr(kr) {
                const items = kr.action_items || [];
                return '<div class="okr-plan-kr"><div class="okr-plan-kr__header"><span class="okr-kr-badge">KR</span><strong>' + this.e(kr.title) +
                        '</strong>' + this.period_badge(kr.period_label) + '<span>' + this.pluralize(items.length, 'Action Item') + '</span><b>' + this.percent(kr.progress) +
                        '</b></div><div class="okr-plan-actions">' + (items.length ? items.map(ai => this.render_plan_action(ai)).join('') :
                        '<div class="okr-plan-tree-empty">' + __('No action items.') + '</div>') + '</div></div>';
        }

        render_plan_action(ai) {
                const checks = ai.checkins || [];
                return '<details class="okr-plan-action"><summary><span class="okr-ai-badge">AI</span><span><strong>' + this.e(ai.title) + '</strong><small>' +
                        this.e(ai.owner || 'Unassigned') + ' &middot; ' + this.e(ai.due_date || '-') + '</small></span><b>' + this.percent(ai.progress) +
                        '</b><span class="okr-status-pill okr-status-pill--' + this.status_slug(ai.status) + '">' + this.e(ai.status || 'Draft') +
                        '</span><em>' + this.pluralize(checks.length, 'Check-in') + '</em></summary><div class="okr-plan-checkins">' +
                        (checks.length ? checks.map(ck => '<div><span>' + this.e(ck.date) + '</span><strong>' + this.percent(ck.progress) + '</strong><p>' +
                        this.e(ck.note || __('No update')) + (ck.blockers ? '<br><b>' + __('Blocker') + ':</b> ' + this.e(ck.blockers) : '') + '</p></div>').join('') :
                        '<div class="okr-plan-tree-empty">' + __('No check-ins yet.') + '</div>') + '</div></details>';
        }


        plan_period(row) {
                return { label: 'Financial Year', value: this.format_financial_year(row.financial_year) || '-' };
        }

        format_financial_year(value) {
                return String(value || '').trim().replace(/(\d{4})\s*[-–—]\s*(\d{4})/, '$1-$2');
        }

        format_admin_datetime(value) {
                const date = this.parse_plan_datetime(value);
                if (!date) return '-';

                const now = new Date();
                const diffMs = now - date;
                if (diffMs >= 0 && diffMs < 60 * 60 * 1000) {
                        const mins = Math.max(1, Math.round(diffMs / (60 * 1000)));
                        return `${mins} ${mins === 1 ? 'minute' : 'minutes'} ago`;
                }
                if (diffMs >= 0 && diffMs < 24 * 60 * 60 * 1000) {
                        const hours = Math.max(1, Math.round(diffMs / (60 * 60 * 1000)));
                        return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
                }

                const time = this.format_plan_time(date);
                const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
                if (date.getFullYear() === yesterday.getFullYear() && date.getMonth() === yesterday.getMonth() && date.getDate() === yesterday.getDate()) {
                        return `Yesterday, ${time}`;
                }
                return `${this.format_plan_date(date)}, ${time}`;
        }

        parse_plan_datetime(value) {
                if (!value) return null;
                if (value instanceof Date) return value;
                const normalized = String(value).trim().replace(' ', 'T').replace(/\.\d+$/, '');
                const parsed = new Date(normalized);
                return Number.isNaN(parsed.getTime()) ? null : parsed;
        }

        format_plan_date(date) {
                return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
        }

        format_plan_time(date) {
                return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        }

        format_plan_datetime(value) {
                return this.format_admin_datetime(value);
        }

        pluralize(count, singular) {
                const total = cint(count || 0);
                return `${total} ${singular}${total === 1 ? '' : 's'}`;
        }
        /* ==========================================================================
           OBJECTIVE DETAIL VIEW RENDER
           ========================================================================== */
        open_objective_detail(row) {
                if (row && row.name) {
                        frappe.route_options = { objective: row.name };
                        frappe.set_route('okr-workspace');
                }
        }

        period_badge(label) {
                return label ? `<span class="okr-period-badge">${this.e(label)}</span>` : '';
        }

        render_detail_html(obj) {
                // Generate proven sample drilldown tree if live sub-items are not fully populated in DB yet
                const krList = this.get_kr_drilldown_list(obj);
                const totalInitiatives = krList.reduce((acc, kr) => acc + (kr.initiatives || []).length, 0);
                const blockedInitiatives = krList.reduce((acc, kr) => acc + (kr.initiatives || []).filter(i => i.status === 'Blocked').length, 0);

                return `
                        <!-- Back Navigation -->
                        <button class="okr-back-link" data-action="back-to-dashboard">← Back to workspace</button>

                        <!-- Objective Header Card -->
                        <section class="okr-detail-head-card">
                                <div class="okr-detail-head__top">
                                        <div class="okr-detail-head__left">
                                                <h1 class="okr-detail-head__title">${this.e(obj.objective)}</h1>
                                                <span class="okr-status-pill okr-status-pill--${this.status_slug(obj.reason || obj.priority || 'Draft')}">${this.e(obj.reason || obj.priority || 'DRAFT')}</span>
                                        </div>
                                        <div class="okr-detail-head__right">
                                                <span class="okr-detail-pct okr-metric-num--${this.progress_severity(obj.progress)}">${this.percent(obj.progress)}</span>
                                                <span class="okr-detail-pct-caption">overall progress</span>
                                        </div>
                                </div>
                                <div class="okr-detail-head__divider"></div>
                                <div class="okr-detail-head__bottom">
                                        <div>
                                                <strong>${this.pluralize(krList.length, 'Key Result')}</strong> · <strong>${this.pluralize(totalInitiatives, 'Initiative')}</strong> · <strong style="color: ${(blockedInitiatives || 0) > 0 ? 'var(--critical)' : 'inherit'};">${this.pluralize(blockedInitiatives, 'Blocked Item')}</strong>
                                        </div>
                                        <div class="okr-dept-owner-pill">
                                                <span class="okr-dept-owner-pill__dot"></span>
                                                <span>${this.e(obj.department || 'Unassigned')} — ${this.e(obj.owner || 'Unassigned')}</span>
                                        </div>
                                </div>
                        </section>

                        ${this.render_progress_legend()}

                        <!-- Key Results Heading -->
                        <h2 style="font-family: var(--font-display); font-weight: 700; font-size: 18px; color: var(--ink); margin: 24px 0 12px 2px;">Key results</h2>

                        <!-- Key Results Expandable Cards -->
                        <div class="okr-kr-list">
                                ${krList.map((kr, krIndex) => `
                                        <div class="okr-kr-card ${krIndex === 0 ? 'expanded' : ''}">
                                                <div class="okr-kr-header" data-kr-toggle>
                                                        <div class="okr-kr-header__left">
                                                                <span class="okr-kr-badge">KR</span>
                                                                <span class="okr-kr-title">${this.e(kr.title)}</span>${this.period_badge(kr.period_label)}
                                                        </div>
                                                        <div class="okr-kr-header__right">
                                                                <div class="okr-kr-bar"><div class="okr-kr-bar__fill" style="width: ${this.progress_width(kr.progress)}%;"></div></div>
                                                                <span class="okr-kr-target-pill">${this.e(kr.target || '-')}</span>
                                                                <span class="okr-chevron"></span>
                                                        </div>
                                                </div>
                                                <div class="okr-kr-body">
                                                        ${(kr.initiatives || []).map((init, iIdx) => `
                                                                <div class="okr-init-row ${iIdx === 0 ? 'trail-open' : ''}">
                                                                        <div class="okr-init-top">
                                                                                <div class="okr-init-top__left">
                                                                                        <span class="okr-ai-badge">AI</span>
                                                                                        <div class="okr-init-info">
                                                                                                <div class="okr-title-with-period"><strong>${this.e(init.name)}</strong>${this.period_badge(init.period_label)}</div>
                                                                                                <div class="okr-init-meta">
                                                                                                        <span class="okr-dept-tag">${this.e(init.department || obj.department || 'Unassigned')}</span>
                                                                                                        <span>${this.e(init.owner || obj.owner)}</span>
                                                                                                        <span>·</span>
                                                                                                        <span>${this.e(init.date || '-')}</span>
                                                                                                </div>
                                                                                        </div>
                                                                                </div>
                                                                                <div class="okr-progress-bar">
                                                                                        <div class="okr-progress-bar__fill okr-progress-bar__fill--${this.progress_severity(init.progress)}" style="width: ${this.progress_width(init.progress)}%;"></div>
                                                                                </div>
                                                                                <span style="font-family: var(--admin-font); font-weight: 700; font-size: 13px; color: var(--ink); text-align: right;">${this.percent(init.progress)}</span>
                                                                                <div style="text-align: right;">
                                                                                        <span class="okr-status-pill okr-status-pill--${this.status_slug(init.status)}">${this.e(init.status)}</span>
                                                                                </div>
                                                                        </div>
                                                                        <div class="okr-init-trail-wrap">
                                                                                <button class="okr-trail-toggle" data-toggle-trail data-count="${(init.checkins || []).length}">
                                                                                        ${iIdx === 0 ? '▾' : '▸'} ${(init.checkins || []).length} check-ins — ${iIdx === 0 ? 'hide trail' : 'view trail'}
                                                                                </button>
                                                                                <div class="okr-trail-notes">
                                                                                        ${(init.checkins || []).map((ck, ckIndex) => `
                                                                                                <div class="okr-trail-note-item">
                                                                                                        <span class="okr-trail-note-item__date">${this.e(ck.date)}</span>
                                                                                                        <span class="okr-trail-note-item__pct">${this.checkin_delta(init.checkins || [], ckIndex)}</span>
                                                                                                        <span class="okr-trail-note-item__text ${ck.is_blocker ? 'is-blocker' : ''}">${this.render_checkin_note(ck.note, ck.is_blocker)}</span>
                                                                                                </div>
                                                                                        `).join('')}
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        `).join('')}
                                                </div>
                                        </div>
                                `).join('')}
                        </div>
                `;
        }

        get_kr_drilldown_list(obj) {
                // If live KRs passed from DB exist with initiatives, use them; otherwise ensure high-fidelity data matching Screenshot 4
                if (obj.key_results && obj.key_results.length) {
                        return obj.key_results;
                }
                return [];
        }

        /* ==========================================================================
           FILTER & HELPER METHODS
           ========================================================================== */
        select_plan(plan) {
                if (!plan) return;
                this.filters.plan = plan;
                this.load();
        }

        clear_plan() {
                this.filters.plan = '';
                this.load();
        }
        toggle_filter_drawer() {
                this.filter_drawer_open = !this.filter_drawer_open;
                const card = this.body.find('.okr-filter-card');
                card.toggleClass('open', this.filter_drawer_open);
        }

        render_filters() {
                const plans = (this.options.plans || []).filter(plan => {
                        if (this.filters.year && plan.financial_year !== this.filters.year) return false;
                        return true;
                });
                this.body.find('[data-filter-bar]').html(`
                        ${this.filter_select('year', __('Financial Year'), this.options.years || [], 'name', 'name')}
                        ${this.filter_select('plan', __('Plan'), plans, 'name', 'plan_name')}
                        ${this.filter_select('department', __('Department'), this.options.departments || [], 'name', 'department_name')}
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
                return `<div class="okr-filter-field"><label>${label}</label><select class="form-control" data-filter="${field}">${options.join('')}</select></div>`;
        }

        render_filter_summary() {
                this.body.find('[data-filter-summary-text]').html(this.get_filter_summary_text());
        }

        get_filter_summary_text() {
                const parts = [];
                if (this.filters.department) parts.push(this.e(this.filters.department));
                else parts.push(__('All Departments'));

                if (this.filters.year) parts.push(this.e(this.filters.year));
                else parts.push(__('All Years'));
                if (this.filters.plan) parts.push(this.e(this.plan_label(this.filters.plan)));
                if (this.filters.status) parts.push(this.e(this.filters.status));
                else parts.push(__('All Statuses'));

                return parts.join(' · ');
        }

        plan_label(plan) {
                const row = (this.options.plans || []).find(item => item.name === plan);
                return row ? (row.plan_name || row.name) : plan;
        }
        compute_health_grade(m) {
                let score = 100;
                const progress = flt(m.company_progress || 0);
                if (progress < 70) score -= (70 - progress);
                if (progress < 40) score -= 15;

                const blocked = cint(m.blocked_objectives || 0);
                score -= Math.min(30, blocked * 3);

                const overdue = cint(m.overdue_action_items || 0);
                score -= Math.min(20, overdue * 1.5);


                score = Math.max(0, Math.round(score * 10) / 10);

                if (score >= 85) return { grade: 'A', label: __('Good'), tone: 'good', score };
                if (score >= 70) return { grade: 'B', label: __('On Track'), tone: 'good', score };
                if (score >= 55) return { grade: 'C', label: __('Needs Work'), tone: 'warning', score };
                if (score >= 40) return { grade: 'D', label: __('At Risk'), tone: 'warning', score };
                return { grade: 'F', label: __('Critical'), tone: 'critical', score };
        }

        severity_slug(tone) {
                const t = String(tone || '').toLowerCase();
                if (t === 'critical' || t === 'red') return 'critical';
                if (t === 'warning' || t === 'amber' || t === 'orange') return 'warning';
                return 'good';
        }

        render_progress_legend() {
                return `
                        <div class="okr-progress-legend" aria-label="${__('Progress color thresholds')}">
                                <span><i class="is-blocked"></i>${__('Blocked')}</span>
                                <span><i class="is-low"></i>${__('0–50%')}</span>
                                <span><i class="is-track"></i>${__('50%+')}</span>
                        </div>
                `;
        }


        checkin_delta(checkins, index) {
                const current = flt((checkins[index] || {}).pct || 0, 1);
                const previous = index < checkins.length - 1 ? flt((checkins[index + 1] || {}).pct || 0, 1) : null;
                if (previous === null) return `${current}%`;
                const delta = flt(current - previous, 1);
                return `${current}% (${delta > 0 ? '+' : ''}${delta}%)`;
        }

        render_checkin_note(note, is_blocker) {
                const safeNote = this.e(note || '');
                if (!is_blocker) return safeNote;
                const match = safeNote.match(/^(.*?)(?:\s*[—-]\s*)?Blocker:\s*(.*)$/i);
                if (!match) return `<span class="okr-blocker-tag">${__('Blocker')}</span><span>${safeNote}</span>`;
                const update = String(match[1] || '').trim();
                const blocker = String(match[2] || '').trim();
                return `${update ? `<span>${update}</span>` : ''}<span class="okr-blocker-tag">${__('Blocker')}</span><span>${blocker}</span>`;
        }

        progress_severity(val) {
                const v = flt(val || 0);
                if (v < 50) return 'critical';
                if (v <= 75) return 'warning';
                return 'good';
        }

        status_slug(status) {
                const s = String(status || '').toLowerCase();
                if (s.includes('block') || s.includes('crit')) return 'critical';
                if (s.includes('overdue') || s.includes('warn') || s.includes('watch') || s.includes('risk') || s.includes('low') || s.includes('hold')) return 'warning';
                if (s.includes('good') || s.includes('healthy') || s.includes('track') || s.includes('complet') || s === 'active' || s === 'open') return 'good';
                if (s.includes('draft') || s.includes('prog') || s.includes('info')) return 'info';
                return 'muted';
        }

        percent(value) {
                return `${flt(value || 0, 1)}%`;
        }

        progress_width(value) {
                return Math.max(2, Math.min(100, flt(value || 0, 1)));
        }

        e(value) {
                return frappe.utils.escape_html(String(value == null ? '' : value));
        }
}
