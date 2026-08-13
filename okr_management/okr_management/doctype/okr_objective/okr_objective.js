frappe.ui.form.on('OKR Objective', {
    setup(frm) {
        frm.set_query('team', 'teams', () => ({
            query: 'okr_management.okr_management.doctype.okr_objective.okr_objective.get_team_options'
        }));
        const team_field = frappe.meta.get_docfield('OKR Objective Team', 'team', frm.doc.name);
        if (team_field) team_field.only_select = 1;
        frm.set_query('parent_plan', () => ({
            query: 'okr_management.okr_management.doctype.okr_objective.okr_objective.search_available_plans',
            filters: { status: ['in', ['Draft', 'Active']] },
        }));
        frm.set_query('level_details', () => {
            if (frm.doc.level === 'Department' && frm.doc.parent_plan) {
                return {
                    query: 'okr_management.okr_management.doctype.okr_objective.okr_objective.search_plan_departments',
                    filters: { parent_plan: frm.doc.parent_plan },
                };
            }
            if (frm.doc.level === 'Individual') {
                return {
                    query: 'okr_management.okr_management.doctype.okr_objective.okr_objective.get_team_options',
                };
            }
            return {};
        });
    },
    onload(frm) {
        sync_level_details(frm);
        configure_level_details(frm, false);
    },
    onload_post_render(frm) {
        if (frm.doc.parent_plan) load_plan_context(frm);
        else render_plan_context_preview(frm, {});
        layout_left_fields(frm);
    },
    refresh(frm) {
        frm.$wrapper.find('.form-dashboard').hide();
        sync_level_details(frm);
        configure_objective_form(frm);
        configure_level_details(frm, false);
        frm.doc.parent_plan ? load_plan_context(frm) : clear_plan_context(frm);
        layout_left_fields(frm);
    },
    parent_plan(frm) {
        load_plan_context(frm);
    },
    level(frm) {
        configure_level_details(frm, true);
    },
    status(frm) {
        configure_objective_form(frm);
    },
    validate(frm) {
        if (['Department', 'Individual'].includes(frm.doc.level) && !frm.doc.level_details) {
            frappe.throw(__('Level Details is required for {0} level.', [frm.doc.level]));
        }
        if (frm.doc.level === 'Team') {
            const teams = (frm.doc.teams || []).map((row) => row.team);
            if (!teams.length) frappe.throw(__('At least one User is required.'));
            if (teams.some((team) => !team)) frappe.throw(__('User rows cannot be empty.'));
            if (new Set(teams).size !== teams.length) frappe.throw(__('Duplicate Users are not allowed.'));
        }
    }
});

function sync_level_details(frm) {
    if (!frm.doc.level_details && frm.doc.level === 'Department' && frm.doc.department) {
        frm.doc.level_details = frm.doc.department;
        frm.refresh_field('level_details');
    }
}


function configure_objective_status(frm, plan_status) {
    const statuses = ['Draft', 'Active', 'On Hold', 'Completed', 'Closed'];
    frm.set_df_property('status', 'options', statuses.join('\n'));
    if (!frm.is_new()) return;
    const required_status = plan_status === 'Active' ? 'Active' : 'Draft';
    if (frm.doc.status !== required_status) frm.set_value('status', required_status);
}

function match_description_heights(frm) {
    ['description', 'plan_description'].forEach((fieldname) => {
        const field = frm.fields_dict[fieldname];
        if (!field || !field.$wrapper) return;
        field.$wrapper.find('textarea, .like-disabled-input').css({
            height: '100px',
            'min-height': '100px',
            'max-height': '100px'
        });
    });
}

function configure_objective_form(frm) {
    [
        'plan_name', 'plan_description', 'company', 'financial_year', 'plan_owner'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));

    frm.set_df_property('context_preview_html', 'label', __('Context Preview'));
    frm.toggle_display('context_preview_html', 1);
    frm.toggle_display('plan_team_preview', 0);
    ['plan_name', 'plan_description', 'company', 'financial_year', 'plan_owner', 'timeline_preview', 'plan_team_preview'].forEach((fieldname) => frm.set_df_property(fieldname, 'hidden', 1));

    const locked = !frm.is_new()
        && ['Active', 'On Hold', 'Completed', 'Closed'].includes(frm.doc.status);
    frm.set_df_property('parent_plan', 'hidden', 0);
    frm.set_df_property('parent_plan', 'reqd', 1);
    frm.toggle_display('parent_plan', true);
    frm.set_df_property('level', 'hidden', 0);
    frm.set_df_property('level', 'reqd', 1);
    frm.set_df_property('level', 'options', 'Organization\nDepartment\nTeam\nIndividual');
    frm.toggle_display('level', true);
    ['parent_plan', 'level', 'level_details', 'teams', 'start_date', 'end_date'].forEach(
        (fieldname) => frm.set_df_property(
            fieldname,
            'read_only',
            locked || (fieldname === 'level_details' && frm.doc.level === 'Individual')
        )
    );
    frm.refresh_field('parent_plan');
    frm.refresh_field('level');
    if (frm.is_new()) {
        ['parent_plan', 'objective_title', 'description', 'level', 'priority', 'status'].forEach((fieldname) => {
            frm.set_df_property(fieldname, 'hidden', 0);
            frm.set_df_property(fieldname, 'read_only', 0);
            frm.toggle_display(fieldname, true);
            frm.toggle_enable(fieldname, true);
            frm.fields_dict[fieldname]?.$wrapper?.show();
            frm.refresh_field(fieldname);
        });
        frm.enable_save();
    }
    setTimeout(() => match_description_heights(frm), 0);

    if (window.okr_management && window.okr_management.ui && window.okr_management.ui.apply_context_panel_style) {
        window.okr_management.ui.apply_context_panel_style(frm);
    }
}

function configure_level_details(frm, clear_value) {
    const doctypes = { Department: 'Department', Individual: 'User' };
    const labels = { Department: __('Department'), Individual: __('Employee') };
    const is_team = frm.doc.level === 'Team';

    if (clear_value) {
        frm.set_value('level_details', '');
        frm.set_value('department', '');
    }
    frm.set_value('level_details_doctype', doctypes[frm.doc.level] || '');
    frm.set_df_property('level_details', 'label', labels[frm.doc.level] || '');
    frm.toggle_display('level_details', ['Department', 'Individual'].includes(frm.doc.level));
    frm.set_df_property('level_details', 'reqd', ['Department', 'Individual'].includes(frm.doc.level));
    frm.set_df_property('level_details', 'read_only', false);
    frm.toggle_display('teams', is_team);

    if (frm.doc.level === 'Organization' || is_team) frm.set_value('level_details', '');
    if (frm.doc.level === 'Individual' && !frm.doc.level_details) frm.set_value('level_details', frappe.session.user);
    if (frm.doc.level === 'Department') frm.set_value('department', frm.doc.level_details || '');

    if (is_team && !(frm.doc.teams || []).length) {
        frm.add_child('teams');
        frm.refresh_field('teams');
    } else if (!is_team && (frm.doc.teams || []).length) {
        frm.clear_table('teams');
        frm.refresh_field('teams');
    }
    frm.refresh_field('level_details');
    setTimeout(() => {
        style_team_grid(frm);
        adjust_left_fields_flex(frm);
    }, 0);
}

function style_team_grid(frm) {
    const grid = frm.fields_dict.teams && frm.fields_dict.teams.grid;
    if (!grid || !grid.wrapper) return;

    const team_field = frappe.meta.get_docfield('OKR Objective Team', 'team', frm.doc.name);
    if (team_field) team_field.only_select = 1;

    grid.wrapper.find('.grid-add-row')
        .text(__('Add User'))
        .removeClass('btn-xs')
        .addClass('btn-sm');
}

function load_plan_context(frm) {
    if (!frm.doc.parent_plan) {
        clear_plan_context(frm);
        return;
    }

    const selected_plan = frm.doc.parent_plan;
    frappe.call({
        method: 'okr_management.okr_management.doctype.okr_plan.okr_plan.get_plan_context',
        args: { plan_name: selected_plan }
    }).then((response) => {
        if (frm.doc.parent_plan !== selected_plan) return;

        const context = response.message || {};
        configure_objective_status(frm, context.status);
        const values = {
            plan_name: context.plan_name || '',
            plan_description: context.description || '',
            company: context.company || '',
            plan_owner: context.plan_owner || '',
            start_date: context.start_date || '',
            end_date: context.end_date || ''
        };
        // Financial Year is derived from the selected Plan and populated again
        // server-side during validation. Avoid client Link permission validation for
        // this hidden context field; OKR Users do not need Fiscal Year access.
        frm.doc.financial_year = context.financial_year || '';
        frm.refresh_field('financial_year');
        frm.set_value(values);
        render_plan_context_preview(frm, context);
        match_description_heights(frm);
    });
}

function clear_plan_context(frm) {
    configure_objective_status(frm, '');
    [
        'plan_name', 'plan_description', 'company', 'financial_year',
        'plan_owner', 'start_date', 'end_date'
    ].forEach((fieldname) => frm.set_value(fieldname, ''));
    render_plan_context_preview(frm, {});
}

function render_plan_context_preview(frm, context) {
    const field = frm.fields_dict.context_preview_html;
    if (!field || !field.$wrapper) return;

    const ctx = context || {};
    let timeline_value = __('Select a Plan to preview its timeline.');
    const start_date = ctx.start_date || frm.doc.start_date;
    const end_date = ctx.end_date || frm.doc.end_date;
    if (start_date && end_date) {
        timeline_value = frappe.datetime.str_to_user(start_date)
            + ' → ' + frappe.datetime.str_to_user(end_date);
        timeline_value += ' • ' + __('{0} Days', [
            frappe.datetime.get_day_diff(end_date, start_date) + 1
        ]).replace(' ', '\u00a0');
    }

    const team_rows = (ctx.members || []).map((member) => {
        const name = frappe.utils.escape_html(member.full_name || member.user || '');
        const role = frappe.utils.escape_html(member.role === 'Admin' ? __('Plan Coordinator') : (member.role || ''));
        return '<li style="margin:0 0 6px;">' + name
            + (role ? ' <span style="color:var(--text-muted); font-size:11px;">(' + role + ')</span>' : '')
            + '</li>';
    }).join('');

    const team_html = team_rows
        ? '<ul style="margin:0;padding-left:18px;">' + team_rows + '</ul>'
        : '<span style="color:var(--text-muted);">' + __('No Plan Team members') + '</span>';

    const icons = {
        tag:      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
        calendar: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
        building: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
        trending: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
        clock:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
        notes:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
        timer:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
        team:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    };

    render_preview_cards(field, [
        { icon: icons.tag,      label: __('Plan Name'),        value: ctx.plan_name || frm.doc.plan_name },
        { icon: icons.calendar, label: __('Financial Year'),   value: ctx.financial_year || frm.doc.financial_year },
        { icon: icons.building, label: __('Organization'),     value: ctx.company || frm.doc.company },
        { icon: icons.trending, label: __('Status'),           value: ctx.status || frm.doc.status },
        { icon: icons.timer,    label: __('Sprint Frequency'), value: ctx.sprint_frequency || frm.doc.sprint_frequency },
        { icon: icons.clock,    label: __('Timeline'),         value: timeline_value },
        { icon: icons.notes,    label: __('Description'),      value: ctx.description || frm.doc.plan_description, wide: true },
        { icon: icons.team,     label: __('Plan Team'),        html: team_html, wide: true },
    ], __('No plan context available.'));
}

function render_preview_cards(field, cards, empty_message) {
    if (window.okr_management && window.okr_management.ui && window.okr_management.ui.render_preview_cards) {
        window.okr_management.ui.render_preview_cards(field, cards, empty_message);
        return;
    }
    if (!field || !field.$wrapper) return;
    const visible_cards = cards || [];
    const escape_html = (val) => frappe.utils.escape_html(String(val ?? "—"));
    const card_html = visible_cards.length
        ? visible_cards.map((card) => {
            if (!card) return "";
            const wide = Boolean(card.wide);
            let val = "—";
            if (card.value !== undefined && card.value !== null && String(card.value).trim() !== "") {
                val = String(card.value);
            }
            const content = card.html
                || '<div style="font-size:13px;font-weight:' + (wide ? '500' : '600') + ';color:#1e293b;line-height:' + (wide ? '1.5' : '1.4') + ';word-break:break-word;white-space:pre-wrap;">'
                    + escape_html(val)
                    + '</div>';
            return '<div style="' + (wide ? 'width:100%;' : 'flex:1 1 45%;min-width:180px;')
                + 'display:flex;align-items:' + (wide ? 'flex-start' : 'center')
                + ';gap:10px;background:#f8f9fc;border:1px solid #e3e8ef;border-radius:10px;padding:10px 14px;">'
                + '<span style="font-size:18px;flex-shrink:0;margin-top:' + (wide ? '2px' : '0') + ';color:#5b6b8a;display:flex;align-items:center;">'
                + (card.icon || "📌") + '</span>'
                + '<div style="min-width:0;">'
                + '<div style="font-size:10px;font-weight:600;color:#8d99ae;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;">'
                + escape_html(__(card.label || "")) + '</div>'
                + content
                + '</div></div>';
        }).join('')
        : '<div style="width:100%;padding:12px 14px;border:1px dashed #d6dbe6;border-radius:10px;color:var(--text-muted);background:#fbfcfe;">'
            + escape_html(empty_message || __("No context available."))
            + '</div>';

    const wrapper_html = '<div style="display:flex;flex-wrap:wrap;gap:12px;">' + card_html + '</div>';
    if (typeof field.set_value === 'function') {
        field.set_value(wrapper_html);
    } else {
        field.$wrapper.html(wrapper_html);
    }
}

function adjust_left_fields_flex(frm) {
    const level = frm.fields_dict.level?.$wrapper;
    const level_details = frm.fields_dict.level_details?.$wrapper;
    if (!level || !level_details) return;
    const show_details = frm.doc.level === 'Department';
    level.css('flex', show_details ? '1 1 calc(50% - 8px)' : '1 1 100%');
}

function layout_left_fields(frm) {
    const level = frm.fields_dict.level?.$wrapper;
    const level_details = frm.fields_dict.level_details?.$wrapper;
    const priority = frm.fields_dict.priority?.$wrapper;
    const status = frm.fields_dict.status?.$wrapper;

    if (!level || !level_details || !priority || !status) return;

    // Create flex row 1 for level and level_details
    if (!level.parent().hasClass('okr-layout-row-1')) {
        const row = $('<div class="okr-layout-row-1" style="display: flex; gap: 16px; margin-bottom: 0px; width: 100%;"></div>');
        level.before(row);
        row.append(level).append(level_details);
        level.css({ 'margin-bottom': '12px', 'min-width': '0' });
        level_details.css({ 'flex': '1 1 calc(50% - 8px)', 'margin-bottom': '12px', 'min-width': '0' });
    }

    // Create flex row 2 for priority and status
    if (!priority.parent().hasClass('okr-layout-row-2')) {
        const row = $('<div class="okr-layout-row-2" style="display: flex; gap: 16px; margin-bottom: 0px; width: 100%;"></div>');
        priority.before(row);
        row.append(priority).append(status);
        priority.css({ 'flex': '1 1 calc(50% - 8px)', 'margin-bottom': '12px', 'min-width': '0' });
        status.css({ 'flex': '1 1 calc(50% - 8px)', 'margin-bottom': '12px', 'min-width': '0' });
    }

    adjust_left_fields_flex(frm);
}
