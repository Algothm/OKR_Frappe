frappe.ui.form.on('OKR Objective', {
    refresh(frm) {
        frm.set_df_property('naming_series', 'hidden', 1);
        set_sprint_query(frm);
        set_static_properties(frm);
        setup_sprint_context(frm);
        apply_lifecycle_locks(frm);
        apply_completion_ui(frm);

        if (frm.is_new() && !frm.doc.status) {
            frm.set_value('status', 'Draft');
        }
        if (!frm.doc.owner_user) {
            frm.set_value('owner_user', frappe.session.user);
        }
        if (!frm.doc.priority) {
            frm.set_value('priority', 'High');
        }
        if (!frm.doc.level) {
            frm.set_value('level', 'Department');
        }
        frm.toggle_reqd('department', true);
        render_sprint_context(frm);
        if (frm.doc.sprint && frm.__okr_sprint_context_loaded !== frm.doc.sprint) {
            inherit_from_sprint(frm);
        }
    },
    sprint(frm) {
        frm.__okr_sprint_name = '';
        frm.__okr_sprint_description = '';
        frm.__okr_plan_name = '';
        frm.__okr_plan_description = '';
        render_sprint_context(frm, Boolean(frm.doc.sprint));
        frm.__okr_sprint_status = '';
        frm.__okr_sprint_owner = '';
        frm.__okr_sprint_context_loaded = '';
        inherit_from_sprint(frm);
    },
    status(frm) {
        apply_lifecycle_locks(frm);
        apply_completion_ui(frm);
    },
    partial_completion_accepted(frm) {
        apply_completion_ui(frm);
    },
    start_date(frm) {
        validate_dates_within_sprint(frm);
        render_sprint_context(frm);
    },
    end_date(frm) {
        validate_dates_within_sprint(frm);
        render_sprint_context(frm);
    }
});

function set_sprint_query(frm) {
    frm.set_query('sprint', () => ({
        filters: {
            status: ['not in', ['Closed', 'Archived']]
        }
    }));
}

function set_static_properties(frm) {
    [
        'naming_series',
        'parent_plan',
        'financial_year',
        'company',
        'plan_owner',
        'sprint_owner',
        'start_date',
        'end_date',
        'progress',
        'key_result_count',
        'confidence'
    ].forEach(fieldname => frm.set_df_property(fieldname, 'read_only', 1));
}

function setup_sprint_context(frm) {
    ['parent_plan', 'company', 'financial_year', 'start_date', 'end_date']
        .forEach(fieldname => frm.toggle_display(fieldname, false));

    const $column = $(frm.wrapper).find('.form-column[data-fieldname="objective_details_col_break"]').first();
    if (!$column.length || $column.find('.okr-sprint-context').length) {
        return;
    }

    $column.addClass('okr-sprint-context-column').append('<div class="okr-sprint-context"></div>');

    if (!document.getElementById('okr-objective-context-style')) {
        $('<style id="okr-objective-context-style">')
            .text(`
                .okr-sprint-context {
                    background: var(--fg-color);
                    border: 1px solid var(--border-color);
                    border-radius: var(--border-radius-lg);
                    padding: 16px;
                    min-height: 180px;
                }
                .okr-sprint-context-grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 14px 18px;
                }
                .okr-context-item--wide,
                .okr-context-section-title,
                .okr-context-description { grid-column: 1 / -1; }
                .okr-context-section-title {
                    border-bottom: 1px solid var(--border-color);
                    color: var(--heading-color);
                    font-size: var(--text-sm);
                    font-weight: 600;
                    padding-bottom: 6px;
                }
                .okr-context-description {
                    background: var(--control-bg);
                    border: 1px solid var(--border-color);
                    border-radius: var(--border-radius);
                    padding: 10px 12px;
                }
                .okr-context-description-text {
                    color: var(--text-color);
                    line-height: 1.55;
                    overflow-wrap: anywhere;
                    white-space: pre-wrap;
                }
                .okr-context-label {
                    color: var(--text-muted);
                    font-size: var(--text-xs);
                    margin-bottom: 4px;
                }
                .okr-context-value {
                    color: var(--text-color);
                    font-weight: 600;
                    overflow-wrap: anywhere;
                }
                .okr-context-period {
                    align-items: center;
                    background: var(--control-bg);
                    border-radius: var(--border-radius);
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    padding: 10px 12px;
                }
                .okr-context-period-note {
                    color: var(--text-muted);
                    font-size: var(--text-xs);
                    font-weight: 400;
                    width: 100%;
                }
                .okr-context-empty {
                    align-items: center;
                    color: var(--text-muted);
                    display: flex;
                    min-height: 146px;
                    justify-content: center;
                    text-align: center;
                }
                @media (max-width: 767px) {
                    .okr-sprint-context-grid { grid-template-columns: 1fr; }
                    .okr-context-item--wide { grid-column: auto; }
                }
            `)
            .appendTo(document.head);
    }
}

function render_sprint_context(frm, loading = false) {
    setup_sprint_context(frm);
    const $context = $(frm.wrapper).find('.form-column[data-fieldname="objective_details_col_break"] .okr-sprint-context').first();
    if (!$context || !$context.length) return;

    if (!frm.doc.sprint) {
        $context.html(`<div class="okr-context-empty">${__('Select a Sprint to preview its plan, organization, financial year, and period.')}</div>`);
        return;
    }

    if (loading) {
        $context.html(`<div class="okr-context-empty">${__('Loading Sprint context...')}</div>`);
        return;
    }

    const start = format_context_date(frm.doc.start_date);
    const end = format_context_date(frm.doc.end_date);
    const duration = get_sprint_duration(frm.doc.start_date, frm.doc.end_date);
    const period = frm.doc.start_date && frm.doc.end_date
        ? `${start} <span aria-hidden="true">&rarr;</span> ${end}`
        : __('Not available');
    const duration_text = duration
        ? __('{0} days, inherited from the selected Sprint', [duration])
        : __('Inherited from the selected Sprint');

    const items = [
        context_section_title(__('Sprint Information')),
        context_item(__('Sprint Name'), frm.__okr_sprint_name || frm.doc.sprint),
        context_item(__('Status'), frm.__okr_sprint_status),
        context_item(__('Owner'), frm.__okr_sprint_owner),
        context_item(__('Sprint Start Date'), start),
        context_item(__('Sprint End Date'), end),
        context_item(__('Duration'), duration ? __('{0} days', [duration]) : __('Not available')),
        `<div class="okr-context-item okr-context-item--wide">
            <div class="okr-context-label">${__('Sprint Period')}</div>
            <div class="okr-context-period">
                <span class="okr-context-value">${period}</span>
                <span class="okr-context-period-note">${escape_context_value(duration_text)}</span>
            </div>
        </div>`,
        context_section_title(__('Plan Information')),
        context_item(__('Parent Plan'), frm.__okr_plan_name || frm.doc.parent_plan),
        context_item(__('Organization'), frm.doc.company),
        context_item(__('Financial Year'), frm.doc.financial_year)
    ];
    const descriptions = [
        context_description(__('Parent Plan Description'), frm.__okr_plan_description),
        context_description(__('Sprint Description'), frm.__okr_sprint_description)
    ].filter(Boolean);
    if (descriptions.length) {
        items.push(context_section_title(__('Descriptions')), ...descriptions);
    }

    $context.html(`<div class="okr-sprint-context-grid">${items.join('')}</div>`);
}

function context_item(label, value) {
    return `<div class="okr-context-item">
        <div class="okr-context-label">${label}</div>
        <div class="okr-context-value">${escape_context_value(value || __('Not available'))}</div>
    </div>`;
}

function context_section_title(title) {
    return `<div class="okr-context-section-title">${title}</div>`;
}

function context_description(label, value) {
    if (!value) return '';
    return `<div class="okr-context-description">
        <div class="okr-context-label">${label}</div>
        <div class="okr-context-description-text">${escape_context_value(value)}</div>
    </div>`;
}

function escape_context_value(value) {
    return frappe.utils.escape_html(String(value));
}

function format_context_date(value) {
    return value ? frappe.datetime.str_to_user(value) : __('Not available');
}

function get_sprint_duration(start_date, end_date) {
    if (!start_date || !end_date) return 0;
    return frappe.datetime.get_day_diff(end_date, start_date) + 1;
}

function inherit_from_sprint(frm) {
    if (!frm.doc.sprint) {
        update_sprint_fields(frm, {});
        return;
    }

    const selected_sprint = frm.doc.sprint;
    frappe.db.get_value('OKR Sprint', selected_sprint, [
        'sprint_name',
        'description',
        'parent_plan',
        'financial_year',
        'company',
        'status',
        'plan_owner',
        'sprint_owner',
        'start_date',
        'end_date'
    ]).then(r => {
        if (frm.doc.sprint !== selected_sprint) return;
        const sprint = r.message || {};
        frm.__okr_sprint_name = sprint.sprint_name || '';
        frm.__okr_sprint_description = sprint.description || '';
        frm.__okr_sprint_status = sprint.status || '';
        frm.__okr_sprint_owner = sprint.sprint_owner || '';
        if (sprint.parent_plan) {
            frappe.db.get_value('OKR Plan', sprint.parent_plan, ['plan_name', 'description']).then(p => {
                if (frm.doc.sprint !== selected_sprint) return;
                const plan_name = p.message ? p.message.plan_name : '';
                frm.__okr_plan_name = plan_name;
                frm.__okr_plan_description = p.message ? p.message.description || '' : '';
                frm.__okr_sprint_context_loaded = selected_sprint;
                if (plan_name) {
                    frappe.utils.add_link_title('OKR Plan', sprint.parent_plan, plan_name);
                }
                update_sprint_fields(frm, sprint);
            });
        } else {
            frm.__okr_plan_name = '';
            frm.__okr_plan_description = '';
            frm.__okr_sprint_context_loaded = selected_sprint;
            update_sprint_fields(frm, sprint);
        }
    });
}

function update_sprint_fields(frm, sprint) {
    const p1 = frm.set_value('parent_plan', sprint.parent_plan || '');
    const p2 = frm.set_value('financial_year', sprint.financial_year || '');
    const p3 = frm.set_value('company', sprint.company || '');
    const p5 = frm.set_value('plan_owner', sprint.plan_owner || '');
    const p6 = frm.set_value('sprint_owner', sprint.sprint_owner || '');
    const p7 = frm.set_value('start_date', sprint.start_date || '');
    const p8 = frm.set_value('end_date', sprint.end_date || '');

    frm.refresh_field('department');

    Promise.all([p1, p2, p3, p5, p6, p7, p8]).then(() => {
        ['parent_plan', 'financial_year', 'company', 'department', 'plan_owner', 'sprint_owner', 'start_date', 'end_date']
            .forEach(fieldname => frm.refresh_field(fieldname));
        render_sprint_context(frm);
    });
}

function validate_dates_within_sprint(frm, sprint_values) {
    if (!frm.doc.sprint || !frm.doc.start_date || !frm.doc.end_date) {
        return;
    }
    const validate = sprint => {
        if (!sprint.start_date || !sprint.end_date) return;
        if (frm.doc.start_date < sprint.start_date) {
            frappe.msgprint(__('Objective Start Date cannot be before Sprint Start Date ({0}).', [frappe.datetime.str_to_user(sprint.start_date)]));
        }
        if (frm.doc.end_date > sprint.end_date) {
            frappe.msgprint(__('Objective End Date cannot be after Sprint End Date ({0}).', [frappe.datetime.str_to_user(sprint.end_date)]));
        }
        if (frm.doc.start_date > frm.doc.end_date) {
            frappe.msgprint(__('Objective End Date cannot be before Start Date.'));
        }
    };
    if (sprint_values) {
        validate(sprint_values);
    } else {
        frappe.db.get_value('OKR Sprint', frm.doc.sprint, ['start_date', 'end_date']).then(r => validate(r.message || {}));
    }
}

function apply_lifecycle_locks(frm) {
    const status = frm.doc.status || 'Draft';
    const setup_locked = ['Active', 'On Hold', 'Completed', 'Closed'].includes(status);
    const active_locked = ['Active', 'On Hold', 'Completed', 'Closed'].includes(status);
    const closed_locked = ['Closed'].includes(status);

    ['parent_plan', 'sprint', 'financial_year', 'company', 'department', 'plan_owner', 'sprint_owner', 'level', 'start_date', 'end_date']
        .forEach(fieldname => frm.set_df_property(fieldname, 'read_only', setup_locked || frm.get_field(fieldname).df.read_only));

    ['objective_title', 'owner_user'].forEach(fieldname => frm.set_df_property(fieldname, 'read_only', active_locked));
    ['priority', 'reviewer', 'description', 'partial_completion_accepted', 'completion_notes']
        .forEach(fieldname => frm.set_df_property(fieldname, 'read_only', closed_locked));

    set_static_properties(frm);
}

function apply_completion_ui(frm) {
    const is_completion_state = ['Completed', 'Closed'].includes(frm.doc.status);
    frm.toggle_display('partial_completion_accepted', is_completion_state);
    frm.toggle_display('completion_notes', is_completion_state && cint(frm.doc.partial_completion_accepted));
}
