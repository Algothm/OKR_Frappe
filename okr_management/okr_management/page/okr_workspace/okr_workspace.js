frappe.pages['okr-workspace'].on_page_load = function(wrapper) {
        wrapper.okr_workspace = new OKRWorkspace(wrapper);
};

frappe.pages['okr-workspace'].on_page_show = function(wrapper) {
        if (wrapper.okr_workspace) wrapper.okr_workspace.load();
};

class OKRWorkspace {
        constructor(wrapper) {
                this.wrapper = wrapper;
                this.page = frappe.ui.make_app_page({ parent: wrapper, single_column: true });
                this.$body = $('<div class="okr-workspace-page"></div>').appendTo(this.page.main);
                this.filters = Object.assign({ year: '', plan: '', level: 'Department', owner: 'me' }, frappe.session.okr_workspace_filters || {});
                this.state = { objectives: {}, key_results: {}, action_history: {}, action_checkin: null, selected_objective: null };
                this.attachment = '';
                this.saving_checkin = false;
                this.render_shell();
                this.bind_events();
                this.load_options();
        }

        render_shell() {
                this.$body.html(`
                        <div class="okr-ws-shell">
                                <aside class="okr-ws-rail">
                                        <div class="okr-ws-brand">${__('OKR Workspace')}</div>
                                        <div class="okr-ws-rail-title">${__('Objectives')}</div>
                                        <div data-objective-rail></div>
                                </aside>
                                <main class="okr-ws-main">
                                        <div class="okr-ws-topbar">
                                                <div class="okr-ws-active-filters" data-active-filters></div>
                                                <button class="okr-icon-filter" data-open-filter title="${__('Filter')}">${frappe.utils.icon('filter', 'sm')}</button>
                                        </div>
                                        <div class="okr-filter-popover" data-filter-popover style="display:none;">
                                                <div class="okr-pop-head"><strong>${__('Filter Context')}</strong><button data-close-filter>${frappe.utils.icon('close', 'sm')}</button></div>
                                                <div class=okr-pop-content>
                                                <div class="okr-filter-group"><label>${__('Financial Year')}</label><div data-year-pills class="okr-pill-row"></div></div>
                                                <div class="okr-filter-group"><label>${__('Plan')}</label><div data-plan-pills class="okr-pill-row okr-pill-row-wrap"></div></div>
                                                <div class="okr-filter-group"><label>${__('Level')}</label><div data-level-pills class="okr-pill-row"></div></div>
                                                <div class="okr-filter-group"><label>${__('Owner')}</label><div data-owner-pills class="okr-pill-row"></div></div>
                                                </div>
                                                <div class="okr-pop-actions"><button class="btn btn-sm btn-default" data-close-filter>${__('Cancel')}</button><button class="btn btn-sm btn-primary" data-apply-filter>${__('Apply Filter')}</button></div>
                                                </div>
                                        <div data-workspace-content></div>
                                </main>
                        </div>
                `);
        }

        bind_events() {
                $(window).off('focus.okr-workspace').on('focus.okr-workspace', () => {
                        if ((frappe.get_route() || [])[0] === 'okr-workspace') this.load();
                });
                this.$body.on('click', '[data-open-filter]', () => this.$body.find('[data-filter-popover]').toggle());
                this.$body.on('click', '[data-close-filter]', () => this.$body.find('[data-filter-popover]').hide());
                this.$body.on('click', '[data-pill]', (e) => {
                        const $pill = $(e.currentTarget);
                        this.filters[$pill.data('field')] = $pill.data('value') || '';
                        this.render_filter_pills();
                });
                this.$body.on('click', '[data-apply-filter]', () => {
                        frappe.session.okr_workspace_filters = Object.assign({}, this.filters);
                        this.$body.find('[data-filter-popover]').hide();
                        this.load();
                });
                this.$body.on('click', '[data-toggle-objective]', (e) => {
                        if ($(e.target).closest('a, button, input, select, textarea').length) return;
                        e.preventDefault();
                        e.stopPropagation();
                        const objName = $(e.currentTarget).data('toggle-objective');
                        const $card = $(e.currentTarget).closest('.okr-objective-card');
                        const $collapse = $card.find('> .okr-collapse');
                        const $chevron = $card.find('.okr-obj-chevron');

                        this.state.objectives[objName] = !this.state.objectives[objName];

                        $collapse.stop(true, true).slideToggle(180);
                        if (this.state.objectives[objName]) {
                                $chevron.removeClass('collapsed').addClass('expanded');
                        } else {
                                $chevron.removeClass('expanded').addClass('collapsed');
                        }
                });
                this.$body.on('click', '[data-toggle-kr]', (e) => {
                        if ($(e.target).closest('a, button, input, select, textarea').length) return;
                        e.preventDefault();
                        e.stopPropagation();
                        const krName = $(e.currentTarget).data('toggle-kr');
                        const $card = $(e.currentTarget).closest('.okr-kr-card');
                        const $collapse = $card.find('> .okr-collapse');
                        const $chevron = $card.find('.okr-kr-chevron');

                        this.state.key_results[krName] = !this.state.key_results[krName];

                        $collapse.stop(true, true).slideToggle(180);
                        if (this.state.key_results[krName]) {
                                $chevron.removeClass('collapsed').addClass('expanded');
                        } else {
                                $chevron.removeClass('expanded').addClass('collapsed');
                        }
                });
                this.$body.on('click', '[data-toggle-history]', (e) => {
                        if ($(e.target).closest('a, button, input, select, textarea').not('.okr-history-toggle').length) return;
                        e.preventDefault();
                        e.stopPropagation();
                        const actionName = $(e.currentTarget).data('toggle-history');
                        const $block = $(e.currentTarget).closest('.okr-action-block');
                        const $collapse = $block.find('> .okr-history-collapse');
                        const $chevron = $(e.currentTarget).find('.okr-history-chevron, .okr-ai-chevron');

                        this.state.action_history[actionName] = !this.state.action_history[actionName];
                        $collapse.stop(true, true).slideToggle(180);
                        $chevron.toggleClass('expanded', this.state.action_history[actionName]);
                        $chevron.toggleClass('collapsed', !this.state.action_history[actionName]);
                        $(e.currentTarget).find('.okr-history-toggle').attr('aria-expanded', this.state.action_history[actionName] ? 'true' : 'false');
                });
                this.$body.on('click', '[data-open-checkin]', (e) => {
                        e.stopPropagation();
                        this.open_checkin($(e.currentTarget).data('open-checkin'));
                });
                this.$body.on('click', '[data-cancel-checkin]', () => { this.state.action_checkin = null; this.render_content(); });
                this.$body.on('click', '[data-save-checkin]', () => this.save_checkin());
                this.$body.on('click', '[data-attach-file]', () => this.attach_file());
                this.$body.on('click', '[data-remove-attachment]', () => { this.attachment = ''; this.render_attachment(); });
                this.$body.on('click', '[data-adjust-filter]', () => this.$body.find('[data-filter-popover]').show());
                this.$body.on('click', '[data-select-objective]', (e) => {
                        e.preventDefault();
                        this.state.selected_objective = $(e.currentTarget).data('select-objective');
                        this.state.objectives[this.state.selected_objective] = true;
                        this.state.action_checkin = null;
                        this.render_content();
                });
                this.$body.on('click', '.okr-open-link', (e) => {
                        e.stopPropagation();
                });
        }

        load_options() {
                frappe.call({
                        method: 'okr_management.okr_management.page.okr_workspace.okr_workspace.get_filter_options',
                        callback: (r) => {
                                this.options = r.message || {};
                                if (!this.filters.year && (this.options.years || []).length) this.filters.year = this.options.years[0].name;
                                this.render_filter_pills();
                                this.load();
                        }
                });
        }

        load() {
                if (frappe.route_options && frappe.route_options.objective) {
                        const target_obj = frappe.route_options.objective;
                        delete frappe.route_options.objective;

                        frappe.db.get_value('OKR Objective', target_obj, ['parent_plan', 'financial_year', 'level']).then(r => {
                                const val = r.message || {};
                                this.filters.year = val.financial_year || '';
                                this.filters.plan = val.parent_plan || '';
                                this.filters.level = val.level || '';
                                this.filters.owner = 'all';
                                this.state.selected_objective = target_obj;
                                this.render_filter_pills();
                                this.load();
                        });
                        return;
                }

                frappe.call({
                        method: 'okr_management.okr_management.page.okr_workspace.okr_workspace.get_workspace_data',
                        args: this.filters,
                        freeze: true,
                        freeze_message: __('Loading OKR Workspace...'),
                        callback: (r) => {
                                this.data = r.message || { objectives: [] };
                                const objectiveNames = (this.data.objectives || []).map(obj => obj.name);
                                if (!objectiveNames.includes(this.state.selected_objective)) {
                                        this.state.selected_objective = objectiveNames[0] || null;
                                }
                                this.state.objectives = {};
                                this.state.key_results = {};
                                (this.data.objectives || []).forEach(obj => {
                                        this.state.objectives[obj.name] = true;
                                        (obj.key_results || []).forEach(kr => {
                                                this.state.key_results[kr.name] = true;
                                        });
                                });
                                this.render_active_filters();
                                this.render_content();
                        }
                });
        }

        render_filter_pills() {
                if (!this.options) return;
                this.render_pill_group('year', (this.options.years || []).slice(0, 4).map(y => ({ label: y.name, value: y.name })));
                this.render_pill_group('plan', [{ label: __('All'), value: '' }].concat((this.options.plans || []).slice(0, 5).map(s => ({ label: s.plan_name || s.name, value: s.name }))));
                this.render_pill_group('level', (this.options.levels || []).map(l => ({ label: __(l), value: l })));
                this.render_pill_group('owner', [{ label: __('Assigned to Me'), value: 'me' }, { label: __('All'), value: 'all' }]);
        }

        render_pill_group(field, items) {
                const selected = this.filters[field] || '';
                this.$body.find(`[data-${field}-pills]`).html(items.map(item => `
                        <button class="okr-filter-pill ${selected === item.value ? 'active' : ''}" data-pill data-field="${field}" data-value="${frappe.utils.escape_html(item.value)}">${frappe.utils.escape_html(item.label)}</button>
                `).join(''));
        }

        render_active_filters() {
                const labels = [this.filters.year, this.plan_label(), this.filters.level || __('All Levels'), this.filters.owner === 'me' ? __('Me') : __('All')];
                this.$body.find('[data-active-filters]').html(labels.filter(Boolean).map(v => `<span>${frappe.utils.escape_html(v)}</span>`).join(''));
        }

        plan_label() {
                const plan = (this.options.plans || []).find(row => row.name === this.filters.plan);
                return plan ? (plan.plan_name || plan.name) : __('All Plans');
        }

        render_content() {
                const objectives = this.data.objectives || [];
                this.render_rail(objectives);
                if (!objectives.length) {
                        this.$body.find('[data-workspace-content]').html(this.empty_state());
                        return;
                }
                const selected = objectives.find(obj => obj.name === this.state.selected_objective) || objectives[0];
                this.state.selected_objective = selected.name;
                this.state.objectives[selected.name] = true;
                (selected.key_results || []).forEach(kr => { this.state.key_results[kr.name] = true; });
                this.$body.find('[data-workspace-content]').html(this.objective_card(selected));
                this.render_attachment();
        }

        render_rail(objectives) {
                const html = objectives.length ? objectives.map(obj => `
                        <a class="okr-rail-objective ${this.state.selected_objective === obj.name ? 'active' : ''}" href="#${obj.name}" data-select-objective="${obj.name}"><span></span><strong>${frappe.utils.escape_html(obj.objective_title || obj.name)}</strong><small>${cint(obj.progress || 0)}% · ${frappe.utils.escape_html(obj.status || '')}</small></a>
                `).join('') : `<div class="okr-rail-empty">${__('No objectives for selected filter')}</div>`;
                this.$body.find('[data-objective-rail]').html(html);
        }

        objective_card(obj) {
                const open = this.state.objectives[obj.name];
                const progress = cint(obj.progress || 0);

                // Summary cards calculation
                const key_results = obj.key_results || [];
                const total_krs = key_results.length;
                const today = this.data.today || frappe.datetime.now_date();

                let blocked_count = 0;
                let at_risk_count = 0;
                let on_track_count = 0;

                key_results.forEach(kr => {
                        if (this.is_kr_blocked(kr)) {
                                blocked_count++;
                        } else if (this.is_kr_at_risk(kr, today)) {
                                at_risk_count++;
                        } else {
                                const kr_progress = flt(kr.target_progress || 0);
                                if (kr_progress >= 70) {
                                        on_track_count++;
                                }
                        }
                });

                return `
                        <section class="okr-objective-card" id="${obj.name}">
                                <div class="okr-objective-head" data-toggle-objective="${obj.name}">
                                        <div><span class="okr-obj-chevron ${open ? 'expanded' : 'collapsed'}"></span><span class="okr-type-dot">OBJ</span><h2>${frappe.utils.escape_html(obj.objective_title || obj.name)}</h2><span class="okr-status okr-${frappe.scrub(obj.status || '')}">${frappe.utils.escape_html(obj.status || '')}</span></div>
                                </div>
                                <div class="okr-collapse ${open ? 'open' : ''}" style="${open ? 'display: block;' : 'display: none;'}">
                                        <div class="okr-summary-cards">
                                                <div class="okr-summary-card">
                                                        <span class="okr-summary-card-label">${__('Key Results')}</span>
                                                        <strong class="okr-summary-card-value">${total_krs}</strong>
                                                </div>
                                                <div class="okr-summary-card">
                                                        <span class="okr-summary-card-label">${__('On Track')}</span>
                                                        <strong class="okr-summary-card-value text-success">${on_track_count}</strong>
                                                </div>
                                                <div class="okr-summary-card">
                                                        <span class="okr-summary-card-label">${__('At Risk')}</span>
                                                        <strong class="okr-summary-card-value text-warning">${at_risk_count}</strong>
                                                </div>
                                                <div class="okr-summary-card">
                                                        <span class="okr-summary-card-label">${__('Blocked')}</span>
                                                        <strong class="okr-summary-card-value text-danger">${blocked_count}</strong>
                                                </div>
                                                <div class="okr-summary-card okr-completion-card">
                                                        <span class="okr-summary-card-label">${__('Completion')}</span>
                                                        <div class="okr-donut-chart">
                                                                <svg class="okr-donut-svg" viewBox="0 0 36 36">
                                                                        <path class="okr-donut-ring" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e2e8f0" stroke-width="3"></path>
                                                                        <path class="okr-donut-segment" stroke="#2563eb" stroke-width="3" stroke-dasharray="${progress}, 100" stroke-linecap="round" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none"></path>
                                                                </svg>
                                                                <div class="okr-donut-number">${progress}%</div>
                                                        </div>
                                                        <span class="okr-summary-card-target">${__('Target: 100%')}</span>
                                                </div>
                                        </div>
                                        ${(obj.key_results || []).map(kr => this.kr_card(kr)).join('')}
                                </div>
                        </section>
                `;
        }

        period_badge(label) {
                return label ? `<span class="okr-period-badge">${frappe.utils.escape_html(label)}</span>` : '';
        }

        kr_card(kr) {
                const open = this.state.key_results[kr.name];
                const progress = flt(kr.target_progress || 0, 2);
                const statusClass = progress >= 80 ? 'good' : progress >= 45 ? 'warn' : 'risk';
                const progressDisplay = this.kr_progress_display(kr);
                const assigneeEmail = kr.assignee || '';
                return `
                        <div class="okr-kr-card">
                                <div class="okr-kr-head" data-toggle-kr="${kr.name}">
                                        <div>
                                                <span class="okr-kr-chevron ${open ? 'expanded' : 'collapsed'}"></span>
                                                <span class="okr-kr-icon">KR</span>
                                                <div style="display: flex; flex-direction: column;">
                                                        <div class="okr-title-with-period"><strong>${frappe.utils.escape_html(kr.key_result_title || kr.name)}</strong>${this.period_badge(kr.period_label)}</div>
                                                        ${assigneeEmail ? `<span style="font-size: 11px; color: #64748b; font-weight: 500; margin-top: 2px;">Assignee: ${frappe.utils.escape_html(assigneeEmail)}</span>` : ''}
                                                </div>
                                        </div>
                                        <div class="okr-kr-meta">
                                                <span class="okr-signal ${statusClass}">${frappe.utils.escape_html(progressDisplay)}</span>
                                        </div>
                                </div>
                                <div class="okr-collapse ${open ? 'open' : ''}" style="${open ? 'display: block;' : 'display: none;'}">${(kr.action_items || []).length ? kr.action_items.map(ai => this.action_row(ai, kr)).join('') : this.no_actions()}</div>
                        </div>
                `;
        }

        action_row(ai, kr) {
                const progress = flt(ai.progress || 0, 2);
                const historyOpen = this.state.action_history[ai.name];
                const checkinOpen = this.state.action_checkin === ai.name;
                const historyCount = (ai.history || []).length;
                const ownerEmail = ai.owner_user || '';
                return `
                        <div class="okr-action-block">
                                <div class="okr-action-row" data-toggle-history="${ai.name}">
                                        <div class="okr-action-title">
                                                <span class="okr-ai-chevron ${historyOpen ? 'expanded' : 'collapsed'}"></span>
                                                <span class="okr-ai-icon">AI</span>
                                                <div style="display: flex; flex-direction: column;">
                                                        <div class="okr-title-with-period"><strong>${frappe.utils.escape_html(ai.action_item_title || ai.name)}</strong>${this.period_badge(ai.period_label)}</div>
                                                        ${ownerEmail ? `<span style="font-size: 11px; color: #64748b; font-weight: 500; margin-top: 2px;">Assignee: ${frappe.utils.escape_html(ownerEmail)}</span>` : ''}
                                                </div>
                                        </div>
                                        <div class="okr-action-meta-col">
                                                <div class="okr-action-due-date">${ai.due_date ? frappe.datetime.str_to_user(ai.due_date) : '-'}</div>
                                                <button type="button" class="okr-history-toggle" aria-expanded="${historyOpen ? 'true' : 'false'}">
                                                        <span class="okr-history-chevron ${historyOpen ? 'expanded' : 'collapsed'}"></span>
                                                        ${historyCount} ${__('Check-ins')}
                                                </button>
                                        </div>
                                        <span class="okr-status ${frappe.scrub(ai.status || '')}">${frappe.utils.escape_html(ai.status || '')}</span>
                                        <div class="okr-action-progress"><div class="okr-bar"><i style="width:${Math.min(100, progress)}%"></i></div><strong>${progress}%</strong></div>
                                        ${ai.can_checkin ? `<button class="btn btn-sm btn-primary-light" data-open-checkin="${ai.name}">${__('+ Check-In')}</button>` : ''}
                                        <a class="okr-open-link" href="/app/okr-action-item/${encodeURIComponent(ai.name)}">${frappe.utils.icon('external-link', 'sm')}</a>
                                </div>
                                ${checkinOpen ? this.checkin_panel(ai, kr) : ''}
                                <div class="okr-history-collapse ${historyOpen ? 'open' : ''}" style="${historyOpen ? 'display: block;' : 'display: none;'}">${this.history_timeline(ai)}</div>
                        </div>
                `;
        }

        checkin_panel(ai, kr) {
                const currentStatus = ai.status || 'In Progress';
                return `
                        <div class="okr-inline-checkin">
                                <div class="okr-inline-context">
                                        ${this.context(__('Key Result'), kr.key_result_title || kr.name)}${this.context(__('Objective'), kr.objective)}${this.context(__('Reported By'), frappe.session.user)}${this.context(__('Current Progress'), `${flt(ai.progress || 0, 2)}%`)}
                                </div>
                                <div class="okr-inline-fields okr-quick-checkin-form">
                                        <div class="okr-checkin-row">
                                                <label>${__('Progress %')} <input class="form-control" type="number" min="0" max="100" step="0.01" data-ws-progress value="${flt(ai.progress || 0, 2)}"></label>
                                                <label>${__('Status')}
                                                        <select class="form-control" data-ws-status>
                                                                <option value="In Progress" ${currentStatus === 'In Progress' ? 'selected' : ''}>${__('In Progress')}</option>
                                                                <option value="Blocked" ${currentStatus === 'Blocked' ? 'selected' : ''}>${__('Blocked')}</option>
                                                                <option value="On Hold" ${currentStatus === 'On Hold' ? 'selected' : ''}>${__('On Hold')}</option>
                                                                <option value="Open" ${currentStatus === 'Open' ? 'selected' : ''}>${__('Open')}</option>
                                                        </select>
                                                </label>
                                        </div>
                                        <label class="okr-update-field">${__('Description / Update')} <textarea class="form-control" rows="4" data-ws-update></textarea></label>
                                        <div class="okr-checkin-bottom-row">
                                                <div class="okr-attach-line"><div data-ws-attachment></div><button class="btn btn-sm btn-default" data-attach-file>${__('Attach File')}</button></div>
                                                <div class="okr-inline-actions"><button class="btn btn-sm btn-default" data-cancel-checkin>${__('Cancel')}</button><button class="btn btn-sm btn-dark" data-save-checkin>${__('Save Check-In')}</button></div>
                                        </div>
                                </div>
                        </div>
                `;
        }

        history_timeline(ai) {
                const rows = ai.history || [];
                if (!rows.length) return `<div class="okr-history-empty">${__('No check-ins yet this sprint')}</div>`;
                return `<div class="okr-history"><div class="okr-history-title">${__('Check-In History')}</div>${rows.map(row => `
                        <div class="okr-history-row"><div><span>${frappe.datetime.str_to_user(row.checkin_date)}</span><strong>${flt(row.progress || 0, 2)}%</strong></div><p>${frappe.utils.escape_html(row.achievements || '')}${row.blockers ? `<br><b>${__('Blocker')}:</b> ${frappe.utils.escape_html(row.blockers)}` : ''}${row.attachment ? `<br><a href="${row.attachment}" target="_blank">${__('Attachment')}</a>` : ''}</p></div>
                `).join('')}</div>`;
        }

        kr_progress_display(kr) {
                const metricType = (kr.metric_type || 'Percentage').toLowerCase();
                const unit = (kr.unit_of_measure || '').trim();
                if (this.is_task_kr(kr, unit)) {
                        return `${this.format_kr_number(kr.completed_action_items)} / ${this.format_kr_number(kr.total_action_items)}`;
                }
                if (metricType === 'percentage') {
                        return `${this.format_kr_number(kr.target_progress || kr.current_value || 0)}%`;
                }
                if (metricType === 'currency') {
                        return `${this.format_kr_currency(kr.current_value, kr.currency)} / ${this.format_kr_currency(kr.target_value, kr.currency)}`;
                }

                const value = `${this.format_kr_number(kr.current_value)} / ${this.format_kr_number(kr.target_value)}`;
                return unit && unit !== '%' ? `${value} ${unit}` : value;
        }

        is_task_kr(kr, unit) {
                const normalizedUnit = (unit || '').toLowerCase();
                return cint(kr.total_action_items || 0) > 0 && /action items?|tasks?|to-dos?|todos?/.test(normalizedUnit);
        }

        format_kr_number(value) {
                const number = flt(value || 0, 2);
                if (Math.abs(number - Math.round(number)) < 0.005) {
                        return Math.round(number).toLocaleString();
                }
                return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
        }

        format_kr_currency(value, currency) {
                if (typeof format_currency === 'function') {
                        const number = flt(value || 0, 2);
                        const decimals = Math.abs(number - Math.round(number)) < 0.005 ? 0 : 2;
                        return format_currency(number, currency, decimals);
                }
                return this.format_kr_number(value);
        }

        context(label, value) { return `<div><span>${label}</span><strong>${frappe.utils.escape_html(value || '-')}</strong></div>`; }
        no_actions() { return `<div class="okr-no-actions">${__('No action items under this Key Result.')}</div>`; }
        empty_state() { return `<div class="okr-empty-workspace"><div class="okr-empty-icon">◎</div><h3>${__('No OKRs found')}</h3><p>${__('No objectives match the current filter. Try a different plan, level, or owner.')}</p><button class="btn btn-primary" data-adjust-filter>${__('Adjust Filter')}</button></div>`; }

        is_kr_blocked(kr) {
                if (kr.status === 'Blocked') return true;
                if ((kr.action_items || []).some(ai => ai.status === 'Blocked')) return true;
                return false;
        }

        is_kr_at_risk(kr, todayStr) {
                if (kr.status === 'At Risk') return true;
                const today = moment(todayStr);
                if (kr.end_date) {
                        const diffDays = moment(kr.end_date).diff(today, 'days');
                        const progress = flt(kr.target_progress || 0);
                        if (diffDays >= 0 && diffDays <= 14 && progress < 100) return true;
                }
                if ((kr.action_items || []).some(ai => {
                        if (ai.status === 'At Risk') return true;
                        if (ai.due_date) {
                                const due = moment(ai.due_date);
                                const isOverdue = due.isBefore(today, 'day');
                                const isCompleted = ai.status === 'Completed' || ai.status === 'Cancelled' || flt(ai.progress || 0) >= 100;
                                if (isOverdue && !isCompleted) return true;

                                const diffDays = due.diff(today, 'days');
                                const progress = flt(ai.progress || 0);
                                if (diffDays >= 0 && diffDays <= 14 && progress < 100) return true;
                        }
                        return false;
                })) {
                        return true;
                }
                return false;
        }

        initials(value) {
                if (!value) return '?';
                const namePart = value.includes('@') ? value.split('@')[0] : value;
                const parts = namePart.trim().split(/[\s.]+/);
                return parts.map(p => p[0]).join('').toUpperCase().slice(0, 2);
        }

        toggle(group, key) { this.state[group][key] = !this.state[group][key]; this.render_content(); }
        open_checkin(action) { this.state.action_checkin = this.state.action_checkin === action ? null : action; this.attachment = ''; this.render_content(); }

        attach_file() {
                new frappe.ui.FileUploader({ allow_multiple: false, on_success: file => { this.attachment = file.file_url; this.render_attachment(); } });
        }

        render_attachment() {
                const html = this.attachment ? `<div class="okr-file-chip"><span>${frappe.utils.escape_html(this.attachment.split('/').pop())}</span><button class="btn btn-xs btn-link" data-remove-attachment>${__('Remove')}</button></div>` : `<span class="text-muted small">${__('Optional proof file')}</span>`;
                this.$body.find('[data-ws-attachment]').html(html);
        }

        save_checkin() {
                if (this.saving_checkin) return;

                const action = this.state.action_checkin;
                const $panel = this.$body.find('.okr-inline-checkin');
                const $button = $panel.find('[data-save-checkin]');
                const progress = flt($panel.find('[data-ws-progress]').val(), 2);
                const update = ($panel.find('[data-ws-update]').val() || '').trim();
                const args = {
                        action_item: action,
                        progress,
                        status: ($panel.find('[data-ws-status]').val() || '').trim(),
                        update,
                        blocker: '',
                        dependency: '',
                        attachment: this.attachment || ''
                };

                if (!action) return frappe.msgprint(__('Please select an Action Item.'));
                if (isNaN(progress) || progress < 0 || progress > 100) return frappe.msgprint(__('Progress must be between 0 and 100.'));
                if (!update) return frappe.msgprint(__('Description / Update is required.'));

                this.saving_checkin = true;
                $button.prop('disabled', true).text(__('Saving...'));

                frappe.call({
                        method: 'okr_management.okr_management.page.okr_workspace.okr_workspace.save_workspace_checkin',
                        args,
                        freeze: true,
                        freeze_message: __('Saving Check-In...'),
                        callback: (r) => {
                                this.saving_checkin = false;
                                $button.prop('disabled', false).text(__('Save Check-In'));
                                if (r.exc) return;

                                const message = (r.message && r.message.name) ? __('Check-In saved: {0}', [r.message.name]) : __('Check-In saved');
                                frappe.show_alert({ message, indicator: 'green' });
                                this.state.action_history[action] = true;
                                this.state.action_checkin = null;
                                this.attachment = '';
                                this.load();
                        },
                        error: () => {
                                this.saving_checkin = false;
                                $button.prop('disabled', false).text(__('Save Check-In'));
                        }
                });
        }

        get_assignee_name(email) {
                if (!email) return '';
                let name = '';
                if (window.frappe && frappe.user_info) {
                        const info = frappe.user_info(email);
                        if (info && info.fullname) name = info.fullname;
                }
                if (!name && window.frappe && frappe.boot && frappe.boot.user_info && frappe.boot.user_info[email]) {
                        name = frappe.boot.user_info[email].fullname;
                }
                if (!name) {
                        if (email.includes('@')) {
                                const username = email.split('@')[0];
                                name = username.split(/[\._-]/).map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
                        } else {
                                name = email;
                        }
                }
                return name;
        }
}

