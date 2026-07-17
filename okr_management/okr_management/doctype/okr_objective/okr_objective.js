frappe.ui.form.on('OKR Objective', {
    setup(frm) {
        frm.set_query('team', 'teams', () => ({
            query: 'okr_management.okr_management.doctype.okr_objective.okr_objective.get_team_options'
        }));
        const team_field = frappe.meta.get_docfield('OKR Objective Team', 'team', frm.doc.name);
        if (team_field) team_field.only_select = 1;
        frm.set_query('parent_plan', () => ({ filters: { status: ['in', ['Draft', 'Active']] } }));
        frm.set_query('level_details', () => frm.doc.level === 'Department' && frm.doc.company
            ? { filters: { company: frm.doc.company } } : {});
    },
    onload(frm) {
        sync_level_details(frm);
        configure_level_details(frm, false);
    },
    refresh(frm) {
        sync_level_details(frm);
        configure_objective_form(frm);
        configure_level_details(frm, false);
        frm.doc.parent_plan ? load_plan_context(frm) : clear_plan_context(frm);
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
            if (!teams.length) frappe.throw(__('At least one Team is required.'));
            if (teams.some((team) => !team)) frappe.throw(__('Team rows cannot be empty.'));
            if (new Set(teams).size !== teams.length) frappe.throw(__('Duplicate Teams are not allowed.'));
        }
    }
});

function sync_level_details(frm) {
    if (!frm.doc.level_details && frm.doc.level === 'Department' && frm.doc.department) {
        frm.doc.level_details = frm.doc.department;
        frm.refresh_field('level_details');
    }
}

function configure_objective_form(frm) {
    [
        'plan_name', 'plan_description', 'company', 'financial_year',
        'start_date', 'end_date', 'plan_owner'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));

    const locked = ['Active', 'On Hold', 'Completed', 'Closed'].includes(frm.doc.status);
    ['parent_plan', 'level', 'level_details', 'teams'].forEach(
        (fieldname) => frm.set_df_property(
            fieldname,
            'read_only',
            locked || (fieldname === 'level_details' && frm.doc.level === 'Individual')
        )
    );
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
    frm.toggle_display('level_details', !['Organization', 'Team'].includes(frm.doc.level));
    frm.set_df_property('level_details', 'reqd', ['Department', 'Individual'].includes(frm.doc.level));
    frm.set_df_property('level_details', 'read_only', frm.doc.level === 'Individual');
    frm.toggle_display('teams', is_team);

    if (frm.doc.level === 'Organization' || is_team) frm.set_value('level_details', '');
    if (frm.doc.level === 'Individual' && !frm.doc.level_details) frm.set_value('level_details', frappe.session.user);
    if (frm.doc.level === 'Department') frm.set_value('department', frm.doc.level_details || '');

    if (is_team && !(frm.doc.teams || []).length) {
        frm.add_child('teams');
        frm.refresh_field('teams');
    }
    frm.refresh_field('level_details');
    setTimeout(() => style_team_grid(frm), 0);
}

function style_team_grid(frm) {
    const grid = frm.fields_dict.teams && frm.fields_dict.teams.grid;
    if (!grid || !grid.wrapper) return;

    const team_field = frappe.meta.get_docfield('OKR Objective Team', 'team', frm.doc.name);
    if (team_field) team_field.only_select = 1;

    grid.wrapper.find('.grid-add-row')
        .text(__('Add Team'))
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
        const values = {
            plan_name: context.plan_name || '',
            plan_description: context.description || '',
            company: context.company || '',
            financial_year: context.financial_year || '',
            plan_owner: context.plan_owner || '',
            start_date: context.start_date || '',
            end_date: context.end_date || ''
        };
        return Promise.all(Object.entries(values).map(([key, value]) => frm.set_value(key, value)))
            .then(() => {
                render_timeline_preview(frm);
                render_plan_team(frm, context.members || []);
            });
    });
}

function clear_plan_context(frm) {
    [
        'plan_name', 'plan_description', 'company', 'financial_year',
        'plan_owner', 'start_date', 'end_date'
    ].forEach((fieldname) => frm.set_value(fieldname, ''));
    render_timeline_preview(frm);
    render_plan_team(frm, []);
}

function render_timeline_preview(frm) {
    const field = frm.fields_dict.timeline_preview;
    if (!field || !field.$wrapper) return;

    let text = __('Select a Plan to preview its timeline.');
    let detail = '';
    if (frm.doc.start_date && frm.doc.end_date) {
        text = frappe.datetime.str_to_user(frm.doc.start_date)
            + ' &rarr; ' + frappe.datetime.str_to_user(frm.doc.end_date);
        detail = __('{0} Days', [
            frappe.datetime.get_day_diff(frm.doc.end_date, frm.doc.start_date) + 1
        ]);
    }

    field.$wrapper.html(
        '<div class="form-group"><div class="control-label">' + __('Timeline Preview')
        + '</div><div class="like-disabled-input" style="height:var(--input-height);'
        + 'min-height:var(--input-height);padding:6px 12px;display:flex;align-items:center;'
        + 'border-radius:var(--border-radius);overflow:hidden;">'
        + '<div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;'
        + 'text-overflow:ellipsis;">' + text
        + (detail ? ' <span style="color:var(--text-muted);">&bull; ' + detail + '</span>' : '')
        + '</div></div></div>'
    );
}

function render_plan_team(frm, members) {
    const field = frm.fields_dict.plan_team_preview;
    if (!field || !field.$wrapper) return;

    const rows = (members || []).map((member) => {
        const name = frappe.utils.escape_html(member.full_name || member.user || '');
        const role = frappe.utils.escape_html(member.role || '');
        return '<li style="margin:0 0 6px;">' + name
            + (role ? ' <span style="color:var(--text-muted);">(' + role + ')</span>' : '')
            + '</li>';
    }).join('');

    const content = rows
        ? '<ul style="margin:0;padding-left:18px;">' + rows + '</ul>'
        : '<span style="color:var(--text-muted);">' + __('No Plan Team members') + '</span>';

    field.$wrapper.html(
        '<div class="form-group"><div class="control-label">' + __('Plan Team')
        + '</div><div class="like-disabled-input" style="min-height:var(--input-height);'
        + 'height:auto;padding:9px 12px;border-radius:var(--border-radius);">'
        + content + '</div></div>'
    );
}
