frappe.provide("okr_management");

frappe.listview_settings["OKR Objective"] = {
    onload(listview) {
        $(listview.page.wrapper).addClass("okr-objective-list");

        // Frappe always promotes title_field to the first (subject) column.
        // Build this list with name as its subject, then restore DocType metadata.
        const setup_columns = listview.setup_columns.bind(listview);
        listview.setup_columns = function () {
            const title_field = this.meta.title_field;
            this.meta.title_field = null;
            setup_columns();
            this.meta.title_field = title_field;
        };
        listview.setup_columns();

        // Frappe counts the hidden tag column toward its responsive limit.
        // Build all meaningful columns before applying the final order.
        if (Number(listview.list_view_settings.total_fields || 0) < 5) {
            listview.list_view_settings.total_fields = 5;
            listview.setup_columns();
        }

        const preferred_order = ["name", "objective_title", "level", "priority"];
        const columns_by_field = new Map(
            listview.columns
                .filter((column) => column.df?.fieldname)
                .map((column) => [column.df.fieldname, column])
        );
        const preferred_columns = preferred_order
            .map((fieldname) => {
                if (columns_by_field.has(fieldname)) return columns_by_field.get(fieldname);
                const df = frappe.meta.get_docfield(listview.doctype, fieldname);
                return df ? { type: "Field", df } : null;
            })
            .filter(Boolean);
        const id_column = preferred_columns.find((column) => column.df?.fieldname === "name");
        const title_column = preferred_columns.find(
            (column) => column.df?.fieldname === "objective_title"
        );
        if (id_column) id_column.type = "Subject";
        if (title_column) title_column.type = "Field";

        const fixed_columns = listview.columns.filter((column) => !column.df?.fieldname);
        const remaining_columns = listview.columns.filter(
            (column) => column.df?.fieldname && !preferred_order.includes(column.df.fieldname)
        );
        listview.columns = [...preferred_columns, ...fixed_columns, ...remaining_columns];
        listview.render_header(true);

        // Frappe can rebuild the default columns after metadata refreshes.
        // Reapply the requested order immediately before every row render.
        const original_before_render = listview.before_render.bind(listview);
        listview.before_render = function () {
            const current_by_field = new Map(
                this.columns
                    .filter((column) => column.df?.fieldname)
                    .map((column) => [column.df.fieldname, column])
            );
            const ordered = preferred_order
                .map((fieldname) => current_by_field.get(fieldname))
                .filter(Boolean);
            const current_id = ordered.find((column) => column.df?.fieldname === "name");
            const current_title = ordered.find(
                (column) => column.df?.fieldname === "objective_title"
            );
            if (current_id) current_id.type = "Subject";
            if (current_title) current_title.type = "Field";
            const non_fields = this.columns.filter((column) => !column.df?.fieldname);
            this.columns = [...ordered, ...non_fields];
            this.render_header(true);
            return original_before_render();
        };

        if (!document.getElementById("okr-objective-list-layout")) {
            $("<style>", { id: "okr-objective-list-layout" })
                .text(`
                    .okr-objective-list .list-row .level-left {
                        min-width: 0;
                        flex: 1 1 auto;
                    }
                    .okr-objective-list .list-row-col:nth-of-type(2) {
                        flex: 0 0 230px !important;
                        min-width: 230px;
                    }
                    .okr-objective-list .list-row-col:nth-of-type(3) {
                        flex: 1 1 420px !important;
                        min-width: 220px;
                    }
                    .okr-objective-list .list-row-col:nth-of-type(4) {
                        flex: 0 0 190px !important;
                        min-width: 160px;
                    }
                    .okr-objective-list .list-row-col:nth-of-type(5) {
                        flex: 0 0 130px !important;
                        min-width: 110px;
                    }
                `)
                .appendTo(document.head);
        }

    },
};

okr_management.preview_attachment = function (file_url) {
    if (!file_url) return;
    let parsed;
    try {
        parsed = new URL(String(file_url), window.location.origin);
    } catch (error) {
        frappe.msgprint(__("Invalid attachment URL."));
        return;
    }
    if (
        parsed.origin !== window.location.origin
        || !(parsed.pathname.startsWith("/files/") || parsed.pathname.startsWith("/private/files/"))
    ) {
        frappe.msgprint(__("Only files uploaded to this site can be previewed."));
        return;
    }
    const preview_url = parsed.pathname + parsed.search;
    const safe_url = frappe.utils.escape_html(preview_url);
    const filename = decodeURIComponent(parsed.pathname.split("/").pop() || __("Attachment"));
    const extension = filename.split(".").pop().toLowerCase();
    const image_types = new Set(["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"]);
    const embedded_url = extension === "pdf" ? safe_url + "#toolbar=0&navpanes=0" : safe_url;
    const preview_html = image_types.has(extension)
        ? '<div style="display:flex;justify-content:center;max-height:72vh;overflow:auto;background:#f7f8fa;padding:12px;border-radius:8px">'
            + '<img src="' + safe_url + '" alt="' + frappe.utils.escape_html(filename) + '" style="max-width:100%;height:auto;object-fit:contain">'
            + '</div>'
        : '<iframe src="' + embedded_url + '" title="' + frappe.utils.escape_html(filename)
            + '" style="width:100%;height:72vh;border:1px solid var(--border-color);border-radius:8px;background:#fff"></iframe>';
    const dialog = new frappe.ui.Dialog({
        title: __("Attachment: {0}", [filename]),
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "attachment_preview" }],
    });
    dialog.fields_dict.attachment_preview.$wrapper.html(preview_html);
    dialog.show();
};

(() => {
    const user_roles = new Set(frappe.user_roles || []);
    const admin_user = frappe.session.user === "Administrator" || user_roles.has("OKR Admin");
    const okr_user = user_roles.has("OKR User");
    const is_admin_ui_user = () => admin_user;
    const is_okr_ui_user = () => okr_user;
    const USER_OKR_LIST_SLUGS = new Set([
        "okr-objective",
        "okr-key-result",
        "okr-action-item",
        "okr-check-in",
    ]);
    const CUSTOM_PAGE_ROUTES = [
        { name: "OKR Management", parent: "", path: () => is_admin_ui_user() ? "/app/admin-workspace" : "/app/okr-workspace" },
        { name: "OKR Workspace", parent: "", path: "/app/okr-workspace" },
        { name: "OKR Admin Workspace", parent: "", path: "/app/admin-workspace" },
        { name: "Plan", parent: "OKR Admin Workspace", path: "/app/okr-plan" },
    ];
    const CUSTOM_PAGE_SLUGS = new Set(["okr-workspace", "admin-workspace"]);
    const fallback_route = is_admin_ui_user()
        ? "admin-workspace"
        : is_okr_ui_user() ? "okr-workspace" : "home";
    frappe.re_route["okr-management"] = fallback_route;
    frappe.re_route["okr-admin-workspace"] = is_admin_ui_user() ? "admin-workspace" : fallback_route;
    frappe.re_route["admin-workspace"] = is_admin_ui_user() ? undefined : fallback_route;
    frappe.re_route["okr-workspace"] = is_okr_ui_user() ? undefined : fallback_route;
    frappe.re_route["plan"] = "okr-plan";
    frappe.re_route["objective"] = "okr-objective";
    frappe.re_route["key-result"] = "okr-key-result";
    frappe.re_route["action-item"] = "okr-action-item";
    frappe.re_route["check-in"] = "okr-check-in";
    localStorage.removeItem("_page:admin-workspace");

    function enforce_okr_route_access() {
        const first = window.location.pathname.replace(/^\/app\//, "").split("/")[0];
        if (USER_OKR_LIST_SLUGS.has(first) && !okr_user) {
            frappe.set_route(fallback_route);
            return;
        }
        if (first === "admin-workspace" && !admin_user) {
            frappe.set_route(fallback_route);
        }
    }

    $(document).on("page-change", enforce_okr_route_access);

    function escape_html(value) {
        return frappe.utils.escape_html(String(value ?? "—"));
    }

    function render_preview_cards(field, cards, empty_message, title) {
    if (!field || !field.$wrapper) return;
    const visible_cards = cards || [];
    const escape_html = (val) => frappe.utils.escape_html(String(val ?? "—"));
    const header_title = title || __("Context and Preview");

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

    const title_html = '<div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:10px;">'
        + escape_html(header_title)
        + '</div>';

    const cards_box_html = '<div style="border:1.5px solid #cbd5e0;border-radius:10px;background:#fafbff;padding:16px 18px;box-shadow:0 1px 6px rgba(0,0,0,0.06);display:flex;flex-wrap:wrap;gap:12px;">'
        + card_html
        + '</div>';

    field.$wrapper.prev('.okr-context-heading').remove();
    $(title_html).addClass('okr-context-heading').insertBefore(field.$wrapper);
    const full_html = cards_box_html;

    if (field.$wrapper && field.$wrapper[0]) {
        field.$wrapper[0].innerHTML = full_html;
    } else if (typeof field.set_value === 'function') {
        field.set_value(full_html);
    }

    if (field.$wrapper) {
        field.$wrapper.css({
            'border': 'none',
            'border-radius': '0',
            'background': 'transparent',
            'padding': '0',
            'box-shadow': 'none',
            'display': 'block'
        });
    }
    }
})();



(() => {
    const OKR_DOCTYPES = new Set([
        "OKR Plan",
        "OKR Objective",
        "OKR Key Result",
        "OKR Action Item",
        "OKR Check In",
    ]);

    function is_okr_route() {
        const route = frappe.get_route ? (frappe.get_route() || []) : [];
        const path = window.location.pathname.replace(/\/$/, "");
        return (
            (["Form", "List"].includes(route[0]) && OKR_DOCTYPES.has(route[1]))
            || ["/app/okr-workspace", "/app/admin-workspace", "/app/okr-admin-workspace"].includes(path)
        );
    }

    function refresh_okr_breadcrumbs() {
        if (!is_okr_route() || !frappe.breadcrumbs?.update) return;
        frappe.breadcrumbs.update();
    }

    function install_okr_breadcrumb_override() {
        if (!frappe.breadcrumbs?.set_workspace_breadcrumb) return false;
        if (frappe.breadcrumbs._okr_direct_breadcrumbs) return true;

        const original =
            frappe.breadcrumbs.set_workspace_breadcrumb.bind(frappe.breadcrumbs);
        frappe.breadcrumbs.set_workspace_breadcrumb = function (breadcrumbs) {
            if (
                breadcrumbs?.module === "OKR Management"
                || OKR_DOCTYPES.has(breadcrumbs?.doctype)
            ) {
                return;
            }
            return original(breadcrumbs);
        };
        frappe.breadcrumbs._okr_direct_breadcrumbs = true;

        $(document).on("page-change route-change", () => {
            setTimeout(refresh_okr_breadcrumbs, 0);
            setTimeout(refresh_okr_breadcrumbs, 100);
        });
        frappe.after_ajax(refresh_okr_breadcrumbs);
        setTimeout(refresh_okr_breadcrumbs, 0);
        setTimeout(refresh_okr_breadcrumbs, 100);
        return true;
    }

    if (!install_okr_breadcrumb_override()) {
        const installer = setInterval(() => {
            if (install_okr_breadcrumb_override()) clearInterval(installer);
        }, 50);
    }
})();

// Keep Connections closed by default on every OKR form.
(() => {
    const OKR_DOCTYPES = new Set([
        "OKR Plan",
        "OKR Objective",
        "OKR Key Result",
        "OKR Action Item",
        "OKR Check In",
    ]);

    function collapse_okr_connections() {
        const route = frappe.get_route ? (frappe.get_route() || []) : [];
        if (route[0] !== "Form" || !OKR_DOCTYPES.has(route[1])) return;

        localStorage.setItem("form-links-closed", "1");
        const links_area = window.cur_frm?.dashboard?.links_area;
        if (links_area && !links_area.is_collapsed()) {
            links_area.collapse(true);
        }
    }

    $(document).on("page-change route-change", () => {
        setTimeout(collapse_okr_connections, 0);
        setTimeout(collapse_okr_connections, 100);
    });
})();

// The document badge already contains the linked-record count.
// Suppress Frappe's separate open-record count after every dashboard refresh.
(() => {
    [
        "OKR Plan",
        "OKR Objective",
        "OKR Key Result",
        "OKR Action Item",
        "OKR Check In",
    ].forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            dashboard_update(frm) {
                frm.$wrapper
                    .find(".form-dashboard .open-notification")
                    .addClass("hidden")
                    .hide();
            },
        });
    });
})();
