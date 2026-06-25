frappe.ui.form.on('OKR Action Item', {
    refresh(frm) {
        frm.set_df_property('naming_series', 'hidden', 1);
        frm.set_df_property('objective', 'read_only', 1);
        frm.set_df_property('cycle', 'read_only', 1);
        frm.set_df_property('department', 'read_only', 1);
    },
    key_result(frm) {
        fill_from_key_result(frm);
    },
    start_date(frm) {
        warn_for_dates(frm);
    },
    due_date(frm) {
        warn_for_dates(frm);
    },
    status(frm) {
        if (frm.doc.status === 'Completed' && !frm.doc.completion_date) {
            frm.set_value('completion_date', frappe.datetime.get_today());
        }
        if (frm.doc.status !== 'Completed' && frm.doc.completion_date) {
            frm.set_value('completion_date', null);
        }
    }
});

function fill_from_key_result(frm) {
    if (!frm.doc.key_result) return;
    frappe.db.get_value('OKR Key Result', frm.doc.key_result, ['objective', 'cycle', 'owner_user', 'start_date', 'end_date']).then(r => {
        const kr = r.message || {};
        if (kr.objective) frm.set_value('objective', kr.objective);
        if (kr.cycle) frm.set_value('cycle', kr.cycle);
        if (kr.owner_user && !frm.doc.owner_user) frm.set_value('owner_user', kr.owner_user);
        if (kr.start_date && !frm.doc.start_date) frm.set_value('start_date', kr.start_date);
        if (kr.end_date && !frm.doc.due_date) frm.set_value('due_date', kr.end_date);
        if (kr.objective) {
            frappe.db.get_value('OKR Objective', kr.objective, ['department']).then(obj => {
                const objective = obj.message || {};
                if (objective.department) frm.set_value('department', objective.department);
            });
        }
    });
}

function warn_for_dates(frm) {
    if (!frm.doc.start_date || !frm.doc.due_date) return;
    if (frappe.datetime.str_to_obj(frm.doc.due_date) < frappe.datetime.str_to_obj(frm.doc.start_date)) {
        frappe.msgprint(__('Action Item Due Date cannot be before Start Date.'));
    }
}
