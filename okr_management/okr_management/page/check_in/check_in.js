frappe.pages['check-in'].on_page_load = function(wrapper) {
        new OKRQuickCheckIn(wrapper);
};

class OKRQuickCheckIn {
        constructor(wrapper) {
                this.wrapper = wrapper;
                this.page = frappe.ui.make_app_page({
                        parent: wrapper,
                        title: __('Check-In'),
                        single_column: true
                });
                this.filters = { show_all: 0, status: '' };
                this.selected = null;
                this.attachment = '';
                this.$body = $('<div class="okr-checkin-page"></div>').appendTo(this.page.main);
                this.page.set_primary_action(__('Refresh'), () => this.load(), 'refresh');
                this.render_shell();
                this.bind_events();
                this.load();
        }

        render_shell() {
                this.$body.html(`
                        <div class="okr-checkin-topbar">
                                <div>
                                        <div class="okr-checkin-eyebrow">${__('Employee Check-In')}</div>
                                        <h2>${__('Pending Action Items')}</h2>
                                </div>
                                <div class="okr-pending-count"><strong data-pending-count>0</strong><span>${__('Action Items Pending')}</span></div>
                        </div>
                        <div class="okr-checkin-filters">
                                <button class="btn btn-sm btn-dark" data-filter="my">${__('My Items')}</button>
                                <button class="btn btn-sm btn-default" data-filter="all">${__('All Items')}</button>
                                <select class="form-control" data-status-filter>
                                        <option value="">${__('All Status')}</option>
                                        <option value="Open">${__('Open')}</option>
                                        <option value="In Progress">${__('In Progress')}</option>
                                        <option value="Blocked">${__('Blocked')}</option>
                                        <option value="Completed">${__('Completed')}</option>
                                </select>
                        </div>
                        <div class="okr-checkin-layout">
                                <section class="okr-checkin-card okr-pending-card">
                                        <div class="okr-table-wrap">
                                                <table class="okr-checkin-table">
                                                        <thead>
                                                                <tr>
                                                                        <th>${__('Action Item')}</th>
                                                                        <th>${__('Key Result')}</th>
                                                                        <th>${__('Progress')}</th>
                                                                        <th>${__('Status')}</th>
                                                                        <th>${__('Last Check-In')}</th>
                                                                        <th>${__('Due Date')}</th>
                                                                        <th>${__('')}</th>
                                                                </tr>
                                                        </thead>
                                                        <tbody data-action-items></tbody>
                                                </table>
                                        </div>
                                </section>
                                <section class="okr-checkin-panel-wrap" data-panel-wrap style="display:none;"></section>
                                <section class="okr-checkin-card">
                                        <div class="okr-card-head"><h3>${__('Recent Check-Ins')}</h3></div>
                                        <div data-recent-checkins class="okr-recent-list"></div>
                                </section>
                        </div>
                `);
        }

        bind_events() {
                this.$body.on('click', '[data-filter]', (event) => {
                        const filter = $(event.currentTarget).data('filter');
                        this.filters.show_all = filter === 'all' ? 1 : 0;
                        this.$body.find('[data-filter]').removeClass('btn-dark').addClass('btn-default');
                        $(event.currentTarget).removeClass('btn-default').addClass('btn-dark');
                        this.load();
                });
                this.$body.on('change', '[data-status-filter]', (event) => {
                        this.filters.status = event.currentTarget.value;
                        this.load();
                });
                this.$body.on('click', '[data-open-checkin]', (event) => {
                        const name = $(event.currentTarget).data('open-checkin');
                        const item = (this.data.action_items || []).find(row => row.name === name);
                        if (item) this.render_panel(item);
                });
                this.$body.on('click', '[data-cancel-checkin]', () => this.close_panel());
                this.$body.on('click', '[data-attach-file]', () => this.attach_file());
                this.$body.on('click', '[data-remove-attachment]', () => {
                        this.attachment = '';
                        this.render_attachment();
                });
                this.$body.on('click', '[data-save-checkin]', () => this.save_checkin());
        }

        load() {
                frappe.call({
                        method: 'okr_management.okr_management.page.check_in.check_in.get_checkin_page_data',
                        args: this.filters,
                        freeze: true,
                        freeze_message: __('Loading Check-In items...'),
                        callback: (r) => {
                                this.data = r.message || { action_items: [], recent_checkins: [], pending_count: 0 };
                                this.render_items();
                                this.render_recent();
                                this.$body.find('[data-pending-count]').text(this.data.pending_count || 0);
                        }
                });
        }

        render_items() {
                const rows = this.data.action_items || [];
                const html = rows.length ? rows.map(row => this.item_row(row)).join('') : `
                        <tr><td colspan="7" class="okr-empty-state">${__('No pending action items found.')}</td></tr>
                `;
                this.$body.find('[data-action-items]').html(html);
        }

        item_row(row) {
                const progress = cint(row.progress || 0);
                const buttonLabel = __('Check-In');
                return `
                        <tr class="${row.overdue ? 'is-overdue' : ''}">
                                <td><strong>${frappe.utils.escape_html(row.action_item_title || '')}</strong>${row.overdue ? `<span class="okr-overdue-pill">${__('Overdue')}</span>` : ''}</td>
                                <td><a href="/app/okr-key-result/${encodeURIComponent(row.key_result || '')}">${frappe.utils.escape_html(row.key_result_title || row.key_result || '')}</a></td>
                                <td><div class="okr-progress-mini"><span>${progress}%</span><div><i style="width:${progress}%"></i></div></div></td>
                                <td><span class="okr-status-pill ${frappe.scrub(row.status || '')}">${frappe.utils.escape_html(row.status || '')}</span></td>
                                <td>${row.last_checkin ? frappe.datetime.str_to_user(row.last_checkin) : '-'}</td>
                                <td>${row.due_date ? frappe.datetime.str_to_user(row.due_date) : '-'}</td>
                                <td><button class="btn btn-sm btn-dark" data-open-checkin="${row.name}">${buttonLabel}</button></td>
                        </tr>
                `;
        }

        render_recent() {
                const rows = this.data.recent_checkins || [];
                const html = rows.length ? rows.map(row => `
                        <div class="okr-recent-item">
                                <div><strong>${frappe.utils.escape_html(row.key_result_title || row.key_result || '')}</strong><p>${frappe.utils.escape_html(row.update || '')}</p></div>
                                <div><span>${cint(row.progress || 0)}%</span><small>${frappe.datetime.str_to_user(row.checkin_date)}</small></div>
                        </div>
                `).join('') : `<div class="okr-empty-state">${__('No recent check-ins yet.')}</div>`;
                this.$body.find('[data-recent-checkins]').html(html);
        }

        render_panel(item) {
                this.selected = item;
                this.attachment = '';
                const progress = flt(item.progress || 0, 2);
                const currentStatus = item.status || 'In Progress';
                this.$body.find('[data-panel-wrap]').show().html(`
                        <section class="okr-checkin-card okr-quick-panel">
                                <div class="okr-panel-head">
                                        <h3>${__('Check-In for Action Item')}: <span>${frappe.utils.escape_html(item.action_item_title || '')}</span></h3>
                                        
                                </div>
                                <div class="okr-panel-grid">
                                        <div class="okr-context-box">
                                                ${this.context_pair(__('Key Result'), item.key_result_title || item.key_result)}
                                                ${this.context_pair(__('Objective'), item.objective_title || item.objective)}
                                                ${this.context_pair(__('Plan'), item.parent_plan)}
                                                ${this.context_pair(__('Sprint'), item.parent_sprint)}
                                                ${this.context_pair(__('Company'), item.company)}
                                                ${this.context_pair(__('Department'), item.department)}
                                                ${this.context_pair(__('Reported By'), frappe.session.user)}
                                                ${this.context_pair(__('Current Progress'), `${progress}%`)}
                                        </div>
                                        <div class="okr-input-grid okr-quick-checkin-form">
                                                <div class="okr-checkin-row">
                                                        <div class="okr-field okr-progress-field"><label>${__('Progress %')} <span>*</span></label><input class="form-control" type="number" min="0" max="100" step="0.01" data-progress value="${progress}"></div>
                                                        <div class="okr-field okr-status-field">
                                                                <label>${__('Status')}</label>
                                                                <select class="form-control" data-status>
                                                                        <option value="In Progress" ${currentStatus === 'In Progress' ? 'selected' : ''}>${__('In Progress')}</option>
                                                                        <option value="Blocked" ${currentStatus === 'Blocked' ? 'selected' : ''}>${__('Blocked')}</option>
                                                                        <option value="On Hold" ${currentStatus === 'On Hold' ? 'selected' : ''}>${__('On Hold')}</option>
                                                                        <option value="Open" ${currentStatus === 'Open' ? 'selected' : ''}>${__('Open')}</option>
                                                                </select>
                                                        </div>
                                                </div>
                                                <div class="okr-field okr-update-field"><label>${__('Description / Update')} <span>*</span></label><textarea class="form-control" rows="5" data-update></textarea></div>
                                                <div class="okr-checkin-bottom-row">
                                                        <div class="okr-field okr-attachment-field"><label>${__('Optional Proof Attachment')}</label><div data-attachment></div><button class="btn btn-sm btn-default" data-attach-file>${__('Attach File')}</button></div>
                                                        <div class="okr-panel-actions"><button class="btn btn-default" data-cancel-checkin>${__('Cancel')}</button><button class="btn btn-dark" data-save-checkin>${__('Save Check-In')}</button></div>
                                                </div>
                                        </div>
                                </div>
                        </section>
                `);
                this.$body.find('[data-update]').focus();
                this.render_attachment();
        }

        context_pair(label, value) {
                return `<div class="okr-context-pair"><span>${label}</span><strong>${frappe.utils.escape_html(value || '-')}</strong></div>`;
        }

        close_panel() {
                this.selected = null;
                this.attachment = '';
                this.$body.find('[data-panel-wrap]').hide().empty();
        }

        attach_file() {
                new frappe.ui.FileUploader({
                        allow_multiple: false,
                        on_success: (file) => {
                                this.attachment = file.file_url;
                                this.render_attachment();
                        }
                });
        }

        render_attachment() {
                const html = this.attachment ? `
                        <div class="okr-file-chip"><span>${frappe.utils.escape_html(this.attachment.split('/').pop())}</span><button class="btn btn-xs btn-link" data-remove-attachment>${__('Remove')}</button></div>
                ` : `<div class="text-muted small">${__('Optional proof: image, PDF, Excel, etc.')}</div>`;
                this.$body.find('[data-attachment]').html(html);
        }

        save_checkin() {
                if (!this.selected) return;
                const $panel = this.$body.find('[data-panel-wrap]');
                const args = {
                        action_item: this.selected.name,
                        progress: $panel.find('[data-progress]').val(),
                        status: $panel.find('[data-status]').val(),
                        update: $panel.find('[data-update]').val(),
                        blocker: '',
                        dependency: '',
                        attachment: this.attachment
                };
                if (!args.update) {
                        frappe.msgprint(__('Description / Update is required.'));
                        return;
                }
                frappe.call({
                        method: 'okr_management.okr_management.page.check_in.check_in.save_quick_checkin',
                        args,
                        freeze: true,
                        freeze_message: __('Saving Check-In...'),
                        callback: (r) => {
                                if (!r.exc) {
                                        frappe.show_alert({ message: __('Check-In saved'), indicator: 'green' });
                                        this.close_panel();
                                        this.load();
                                }
                        }
                });
        }
}
