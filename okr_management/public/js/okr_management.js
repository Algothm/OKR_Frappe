frappe.provide("okr_management");

(() => {
    const RAW_OKR_LIST_SLUGS = new Set([
        "okr-plan",
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
    const fallback_route = is_admin_ui_user() ? "admin-workspace" : "okr-workspace";
    frappe.re_route["okr-management"] = fallback_route;
    frappe.re_route["okr-admin-workspace"] = "admin-workspace";
    frappe.re_route["admin-workspace"] = is_admin_ui_user() ? undefined : "okr-workspace";
    frappe.re_route["okr-workspace"] = is_admin_ui_user() ? "admin-workspace" : undefined;
    frappe.re_route["plan"] = "okr-plan";
    frappe.re_route["objective"] = "okr-objective";
    frappe.re_route["key-result"] = "okr-key-result";
    frappe.re_route["action-item"] = "okr-action-item";
    frappe.re_route["check-in"] = "okr-check-in";
    localStorage.removeItem("_page:admin-workspace");

    function escape_html(value) {
        return frappe.utils.escape_html(String(value ?? "—"));
    }

    function render_preview_cards(field, cards, empty_message) {
        if (!field || !field.$wrapper) return;

        const visible_cards = cards || [];

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

        // Title + cards as a single HTML block
        const full_html =
            '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
            + 'letter-spacing:0.08em;margin-bottom:12px;padding-bottom:8px;'
            + 'border-bottom:1px solid #e2e8f0;">'
            + __('Context and Preview')
            + '</div>'
            + '<div style="display:flex;flex-wrap:wrap;gap:12px;">' + card_html + '</div>';

        // Set content directly on the DOM node (most reliable for HTML fields)
        field.$wrapper[0].innerHTML = full_html;

        // Style field.$wrapper (.frappe-control div) as the outer bordered container
        // This is the REAL structural parent of all cards in the DOM
        field.$wrapper.css({
            'border': '1.5px solid #cbd5e0',
            'border-radius': '10px',
            'background': '#fafbff',
            'padding': '16px 18px',
            'box-shadow': '0 1px 6px rgba(0,0,0,0.06)',
            'display': 'block'
        });
    }

    function render_timeline_preview_card(field, title, value, detail, is_error = false) {
        if (!field || !field.$wrapper) return;

        const main_color = is_error ? 'var(--red-600)' : 'var(--text-color)';
        const detail_color = is_error ? 'var(--red-600)' : 'var(--text-muted)';
        const secondary = detail
            ? '<span style="color:var(--text-muted);"> &bull; </span><span style="font-weight:500;color:' + detail_color + ';">'
                + escape_html(detail)
                + '</span>'
            : '';

        const wrapper_html = '<div class="form-group">'
            + '<div class="control-label">' + escape_html(title) + '</div>'
            + '<div class="like-disabled-input" style="height:var(--input-height);min-height:var(--input-height);padding:6px 12px;display:flex;align-items:center;border-radius:var(--border-radius);overflow:hidden;">'
            + '<div style="font-size:13px;font-weight:600;color:' + main_color + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            + escape_html(value || '') + secondary
            + '</div></div></div>';
        if (typeof field.set_value === 'function') {
            field.set_value(wrapper_html);
        } else {
            field.$wrapper.html(wrapper_html);
        }
    }

    okr_management.ui = Object.assign({}, okr_management.ui, {
        render_preview_cards,
        render_timeline_preview_card,
        apply_context_panel_style,
    });

    function apply_context_panel_style(frm) {
        // Safety-net: re-apply border to field.$wrapper in case render_preview_cards
        // hasn't been called yet (e.g., when action item is not yet selected)
        function do_apply() {
            const anchor = frm.fields_dict.context_preview_html;
            if (!anchor || !anchor.$wrapper) return;
            anchor.$wrapper.css({
                'border': '1.5px solid #cbd5e0',
                'border-radius': '10px',
                'background': '#fafbff',
                'padding': '16px 18px',
                'box-shadow': '0 1px 6px rgba(0,0,0,0.06)',
                'display': 'block'
            });
        }
        setTimeout(do_apply, 200);
        setTimeout(do_apply, 700);
    }


    function selector(name, parent) {
        return '.sidebar-item-container[item-name="' + CSS.escape(name) + '"][item-parent="' + CSS.escape(parent) + '"]';
    }

    function get_item(name, parent) {
        return jQuery(selector(name, parent)).first();
    }

    function find_custom_route(target) {
        const anchor = target.closest && target.closest(".desk-sidebar-item > .item-anchor");
        if (!anchor) return null;

        const item = anchor.closest(".sidebar-item-container");
        if (!item) return null;

        return CUSTOM_PAGE_ROUTES.find(
            ({ name, parent }) =>
                item.getAttribute("item-name") === name && item.getAttribute("item-parent") === parent
        );
    }

    function is_admin_ui_user() {
        return frappe.session.user === "Administrator";
    }

    function separated_route(route_parts) {
        const parts = Array.isArray(route_parts) ? route_parts : [];
        const first = String(parts[0] || "").toLowerCase();
        const admin_user = is_admin_ui_user();

        if (parts.length === 1 && first === "okr-management") {
            return [admin_user ? "admin-workspace" : "okr-workspace"];
        }

        if (parts.length === 1 && RAW_OKR_LIST_SLUGS.has(first) && !admin_user) {
            return ["okr-workspace"];
        }
        if (parts.length === 1 && first === "okr-workspace" && admin_user) return ["admin-workspace"];
        if (parts.length === 1 && first === "admin-workspace" && !admin_user) return ["okr-workspace"];
        return parts;
    }

    okr_management.navigation = Object.assign({}, okr_management.navigation, {
        is_admin_ui_user,
        resolve_route: separated_route,
    });

    function patch_router() {
        if (!frappe.router || frappe.router._okrCustomPageRoutePatch) return false;

        const convert_to_standard_route = frappe.router.convert_to_standard_route.bind(frappe.router);
        frappe.router.convert_to_standard_route = async function (route) {
            const route_parts = separated_route(
                Array.isArray(route) ? route : this.get_sub_path_string(route).split("/")
            );
            if (CUSTOM_PAGE_SLUGS.has(route_parts[0])) {
                return route_parts;
            }

            return convert_to_standard_route(route);
        };
        frappe.router._okrCustomPageRoutePatch = true;
        return true;
    }

    function update_custom_page_links() {
        CUSTOM_PAGE_ROUTES.forEach(({ name, parent, path }) => {
            const destination = typeof path === "function" ? path() : path;
            get_item(name, parent).find("> .desk-sidebar-item > .item-anchor").attr("href", destination);
        });
    }

    function enforce_sidebar_separation() {
        const admin_user = is_admin_ui_user();
        const hidden_names = admin_user
            ? ["OKR Workspace", "OKR Objective Execution", "OKR Key Result Execution", "OKR Action Item Execution", "Check-In"]
            : ["Admin Workspace", "OKR Plan Planning", "OKR Sprint Planning"];

        hidden_names.forEach((name) => {
            jQuery('.sidebar-item-container[item-name="' + CSS.escape(name) + '"]').remove();
        });
    }

    function bind_okr_sidebar() {
        patch_router();
        update_custom_page_links();
        enforce_sidebar_separation();
    }

    function schedule_bind() {
        setTimeout(bind_okr_sidebar, 100);
        setTimeout(bind_okr_sidebar, 500);
    }

    const router_patch_interval = setInterval(() => {
        if (patch_router()) {
            clearInterval(router_patch_interval);
        }
    }, 50);

    patch_router();
    document.addEventListener(
        "click",
        (event) => {
            const route = find_custom_route(event.target);
            if (!route) return;

            event.preventDefault();
            event.stopImmediatePropagation();
            window.location.assign(typeof route.path === "function" ? route.path() : route.path);
        },
        true
    );

    jQuery(document).on("page-change route-change", schedule_bind);
    frappe.after_ajax(schedule_bind);

    jQuery(document).ready(() => {
        patch_router();
        new MutationObserver(schedule_bind).observe(document.body, { childList: true, subtree: true });
        schedule_bind();
    });
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
