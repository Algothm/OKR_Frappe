frappe.pages['okr-analytics'].on_page_load = function(wrapper) {
        new OKRWorkspace(wrapper);
};

class OKRWorkspace {
        constructor(wrapper) {
                this.wrapper = wrapper;
                this.page = frappe.ui.make_app_page({ parent: wrapper, title: __('OKR Workspace'), single_column: true });
                this.$body = $('<div class="okr-workspace-page"></div>').appendTo(this.page.main);
                this.filters = Object.assign({ year: '', quarter: '', sprint: '', level: 'Department', owner: 'me' }, frappe.session.okr_workspace_filters || {});
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
                                        <div class="okr-ws-brand"><span></span>${__('OKR Workspace')}</div>
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
                                                <div class="okr-filter-group"><label>${__('Year')}</label><div data-year-pills class="okr-pill-row"></div></div>
                                                <div class="okr-filter-group"><label>${__('Quarter')}</label><div data-quarter-pills class="okr-pill-row"></div></div>
                                                <div class="okr-filter-group"><label>${__('Sprint')}</label><div data-sprint-pills class="okr-pill-row okr-pill-row-wrap"></div></div>
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
                this.$body.on('click', '[data-toggle-objective]', (e) => this.toggle('objectives', $(e.currentTarget).data('toggle-objective')));
                this.$body.on('click', '[data-toggle-kr]', (e) => this.toggle('key_results', $(e.currentTarget).data('toggle-kr')));
                this.$body.on('click', '[data-toggle-history]', (e) => this.toggle('action_history', $(e.currentTarget).data('toggle-history')));
                this.$body.on('click', '[data-open-checkin]', (e) => this.open_checkin($(e.currentTarget).data('open-checkin')));
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
        }

        load_options() {
                frappe.call({
                        method: 'okr_management.okr_management.page.okr_analytics.okr_analytics.get_filter_options',
                        callback: (r) => {
                                this.options = r.message || {};
                                if (!this.filters.year && (this.options.years || []).length) this.filters.year = this.options.years[0].name;
                                this.render_filter_pills();
                                this.load();
                        }
                });
        }

        load() {
                frappe.call({
                        method: 'okr_management.okr_management.page.okr_analytics.okr_analytics.get_workspace_data',
                        args: this.filters,
                        freeze: true,
                        freeze_message: __('Loading OKR Workspace...'),
                        callback: (r) => {
                                this.data = r.message || { objectives: [] };
                                const objectiveNames = (this.data.objectives || []).map(obj => obj.name);
                                if (!objectiveNames.includes(this.state.selected_objective)) {
                                        this.state.selected_objective = objectiveNames[0] || null;
                                }
                                (this.data.objectives || []).forEach(obj => {
                                        if (this.state.objectives[obj.name] === undefined) this.state.objectives[obj.name] = true;
                                        (obj.key_results || []).forEach(kr => {
                                                if (this.state.key_results[kr.name] === undefined) this.state.key_results[kr.name] = true;
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
                this.render_pill_group('quarter', [{ label: __('All'), value: '' }].concat((this.options.quarters || []).map(q => ({ label: q, value: q }))));
                this.render_pill_group('sprint', [{ label: __('All'), value: '' }].concat((this.options.sprints || []).slice(0, 5).map(s => ({ label: s.sprint_name || s.name, value: s.name }))));
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
                const labels = [this.filters.year, this.filters.quarter || __('All Quarters'), this.sprint_label(), this.filters.level || __('All Levels'), this.filters.owner === 'me' ? __('Me') : __('All')];
                this.$body.find('[data-active-filters]').html(labels.filter(Boolean).map(v => `<span>${frappe.utils.escape_html(v)}</span>`).join(''));
        }

        sprint_label() {
                const sprint = (this.options.sprints || []).find(s => s.name === this.filters.sprint);
                return sprint ? (sprint.sprint_name || sprint.name) : __('All Sprints');
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
                return `
                        <section class="okr-objective-card" id="${obj.name}">
                                <div class="okr-objective-head" data-toggle-objective="${obj.name}">
                                        <div><span class="okr-type-dot">OBJ</span><h2>${frappe.utils.escape_html(obj.objective_title || obj.name)}</h2><span class="okr-status okr-${frappe.scrub(obj.status || '')}">${frappe.utils.escape_html(obj.status || '')}</span></div>
                                        <div class="okr-gap-score"><small>${__('Progress')}</small><strong>${progress}%</strong></div>
                                </div>
                                <div class="okr-collapse ${open ? 'open' : ''}">${(obj.key_results || []).map(kr => this.kr_card(kr)).join('')}</div>
                        </section>
                `;
        }

        kr_card(kr) {
                const open = this.state.key_results[kr.name];
                const progress = flt(kr.target_progress || 0, 2);
                const statusClass = progress >= 80 ? 'good' : progress >= 45 ? 'warn' : 'risk';
                return `
                        <div class="okr-kr-card">
                                <div class="okr-kr-head" data-toggle-kr="${kr.name}">
                                        <div><span class="okr-kr-icon">KR</span><strong>${frappe.utils.escape_html(kr.key_result_title || kr.name)}</strong></div>
                                </div>
                                <div class="okr-bar"><i style="width:${Math.min(100, progress)}%"></i></div>
                                <div class="okr-collapse ${open ? 'open' : ''}">${(kr.action_items || []).length ? kr.action_items.map(ai => this.action_row(ai, kr)).join('') : this.no_actions()}</div>
                        </div>
                `;
        }

        action_row(ai, kr) {
                const progress = flt(ai.progress || 0, 2);
                const historyOpen = this.state.action_history[ai.name];
                const checkinOpen = this.state.action_checkin === ai.name;
                return `
                        <div class="okr-action-block">
                                <div class="okr-action-row">
                                        <div class="okr-action-title"><span class="okr-ai-icon">AI</span><div><strong>${frappe.utils.escape_html(ai.action_item_title || ai.name)}</strong><small>${ai.due_date ? frappe.datetime.str_to_user(ai.due_date) : '-'} · <button data-toggle-history="${ai.name}">${(ai.history || []).length} ${__('check-ins')}</button></small></div></div>
                                        <div class="okr-owner"><span>${this.initials(ai.owner_user)}</span>${frappe.utils.escape_html(ai.owner_user || '')}</div>
                                        <span class="okr-status ${frappe.scrub(ai.status || '')}">${frappe.utils.escape_html(ai.status || '')}</span>
                                        <div class="okr-action-progress"><div class="okr-bar"><i style="width:${Math.min(100, progress)}%"></i></div><strong>${progress}%</strong></div>
                                        <button class="btn btn-sm btn-primary-light" data-open-checkin="${ai.name}">${__('+ Check-In')}</button>
                                        <a class="okr-open-link" href="/app/okr-action-item/${encodeURIComponent(ai.name)}">${frappe.utils.icon('external-link', 'sm')}</a>
                                </div>
                                ${checkinOpen ? this.checkin_panel(ai, kr) : ''}
                                ${historyOpen ? this.history_timeline(ai) : ''}
                        </div>
                `;
        }

        checkin_panel(ai, kr) {
                return `
                        <div class="okr-inline-checkin">
                                <div class="okr-inline-context">
                                        ${this.context(__('Key Result'), kr.key_result_title || kr.name)}${this.context(__('Objective'), kr.objective)}${this.context(__('Reported By'), frappe.session.user)}${this.context(__('Current Progress'), `${flt(ai.progress || 0, 2)}%`)}
                                </div>
                                <div class="okr-inline-fields">
                                        <label>${__('Progress %')} <input class="form-control" type="number" min="0" max="100" step="0.01" data-ws-progress value="${flt(ai.progress || 0, 2)}"></label>
                                        <label>${__('Description / Update')} <textarea class="form-control" rows="2" data-ws-update></textarea></label>
                                        <label>${__('Blocker')} <textarea class="form-control" rows="2" data-ws-blocker></textarea></label>
                                        <label>${__('Dependency')} <textarea class="form-control" rows="2" data-ws-dependency></textarea></label>
                                        <div class="okr-attach-line"><div data-ws-attachment></div><button class="btn btn-sm btn-default" data-attach-file>${__('Attach File')}</button></div>
                                </div>
                                <div class="okr-inline-actions"><button class="btn btn-sm btn-default" data-cancel-checkin>${__('Cancel')}</button><button class="btn btn-sm btn-dark" data-save-checkin>${__('Save Check-In')}</button></div>
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

        context(label, value) { return `<div><span>${label}</span><strong>${frappe.utils.escape_html(value || '-')}</strong></div>`; }
        no_actions() { return `<div class="okr-no-actions">${__('No action items under this Key Result.')}</div>`; }
        empty_state() { return `<div class="okr-empty-workspace"><div class="okr-empty-icon">◎</div><h3>${__('No OKRs found')}</h3><p>${__('No objectives match the current filter. Try a different quarter, level, or owner.')}</p><button class="btn btn-primary" data-adjust-filter>${__('Adjust Filter')}</button></div>`; }
        initials(value) { return (value || '?').trim().charAt(0).toUpperCase(); }

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
                        update,
                        blocker: ($panel.find('[data-ws-blocker]').val() || '').trim(),
                        dependency: ($panel.find('[data-ws-dependency]').val() || '').trim(),
                        attachment: this.attachment || ''
                };

                if (!action) return frappe.msgprint(__('Please select an Action Item.'));
                if (isNaN(progress) || progress < 0 || progress > 100) return frappe.msgprint(__('Progress must be between 0 and 100.'));
                if (!update) return frappe.msgprint(__('Description / Update is required.'));

                this.saving_checkin = true;
                $button.prop('disabled', true).text(__('Saving...'));

                frappe.call({
                        method: 'okr_management.okr_management.page.okr_analytics.okr_analytics.save_workspace_checkin',
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
}
