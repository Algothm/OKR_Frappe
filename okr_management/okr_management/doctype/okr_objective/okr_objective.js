frappe.ui.form.on('OKR Objective', {
    refresh(frm) {
        configure_objective_form(frm);
        if (frm.doc.parent_plan) {
            load_plan_context(frm);
        }
    },
    parent_plan(frm) {
        load_plan_context(frm);
    },
    start_date(frm) {
        validate_objective_dates(frm);
    },
    end_date(frm) {
        validate_objective_dates(frm);
    },
    status(frm) {
        configure_objective_form(frm);
    }
});

function configure_objective_form(frm) {
    frm.set_query('parent_plan', () => ({
        filters: { status: ['in', ['Draft', 'Active']] }
    }));
    frm.set_query('department', () => (
        frm.doc.company ? { filters: { company: frm.doc.company } } : {}
    ));

    const inherited_fields = ['financial_year', 'company', 'plan_owner'];
    inherited_fields.forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));

    const setup_locked = ['Active', 'On Hold', 'Completed', 'Closed'].includes(frm.doc.status);
    ['parent_plan', 'level', 'department'].forEach(
        (fieldname) => frm.set_df_property(fieldname, 'read_only', setup_locked)
    );
    frm.set_df_property('progress', 'read_only', 1);
    frm.set_df_property('key_result_count', 'read_only', 1);
}

function load_plan_context(frm) {
    if (!frm.doc.parent_plan) {
        ['financial_year', 'company', 'plan_owner', 'start_date', 'end_date'].forEach(
            (fieldname) => frm.set_value(fieldname, '')
        );
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
            financial_year: context.financial_year || '',
            company: context.company || '',
            plan_owner: context.plan_owner || '',
            start_date: context.start_date || '',
            end_date: context.end_date || ''
        };
        return Promise.all(
            Object.entries(values).map(([fieldname, value]) => frm.set_value(fieldname, value))
        );
    });
}

function validate_objective_dates(frm) {
    if (!frm.doc.parent_plan || !frm.doc.start_date || !frm.doc.end_date) return;
    frappe.call({
        method: 'okr_management.okr_management.doctype.okr_plan.okr_plan.get_plan_context',
        args: { plan_name: frm.doc.parent_plan }
    }).then((response) => {
        const context = response.message || {};
        if (context.start_date && frm.doc.start_date < context.start_date) {
            frappe.msgprint(__('Objective Start Date cannot be before the Plan period start date ({0}).', [
                frappe.datetime.str_to_user(context.start_date)
            ]));
        }
        if (context.end_date && frm.doc.end_date > context.end_date) {
            frappe.msgprint(__('Objective End Date cannot be after the Plan period end date ({0}).', [
                frappe.datetime.str_to_user(context.end_date)
            ]));
        }
    });
}
