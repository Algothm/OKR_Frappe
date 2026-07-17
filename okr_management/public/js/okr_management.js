frappe.provide("okr_management");

(() => {
    const OKR_GROUPS = new Set(["Planning", "Execution", "Administration"]);
    const CUSTOM_PAGE_ROUTES = [
        { name: "OKR Workspace", parent: "Execution", path: "/app/okr-workspace" },
        { name: "Admin Workspace", parent: "Planning", path: "/app/admin-workspace" },
    ];
    const DIRECT_LIST_ROUTES = [
        { name: "Check-In", parent: "OKR Workspace", path: "/app/okr-check-in" },
    ];
    const CUSTOM_PAGE_SLUGS = new Set(["okr-workspace", "admin-workspace"]);
    localStorage.removeItem("_page:admin-workspace");

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

        return [...CUSTOM_PAGE_ROUTES, ...DIRECT_LIST_ROUTES].find(
            ({ name, parent }) =>
                item.getAttribute("item-name") === name && item.getAttribute("item-parent") === parent
        );
    }

    function patch_router() {
        if (!frappe.router || frappe.router._okrCustomPageRoutePatch) return false;

        const convert_to_standard_route = frappe.router.convert_to_standard_route.bind(frappe.router);
        frappe.router.convert_to_standard_route = async function (route) {
            const route_parts = Array.isArray(route) ? route : this.get_sub_path_string(route).split("/");
            if (CUSTOM_PAGE_SLUGS.has(route_parts[0])) {
                return route_parts;
            }

            return convert_to_standard_route(route);
        };
        frappe.router._okrCustomPageRoutePatch = true;
        return true;
    }

    function bind_group_toggle(name) {
        const item = get_item(name, "OKR Management");
        if (item.length === 0 || item.data("okrGroupToggleBound")) return;

        item.data("okrGroupToggleBound", true);
        item.find("> .desk-sidebar-item > .item-anchor").on("click.okr_group_toggle", (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            item.find("> .desk-sidebar-item .drop-icon").trigger("click");
        });
    }


    function normalize_workspace_position() {
        const root_item = get_item("OKR Workspace", "OKR Management");
        const execution_item = get_item("Execution", "OKR Management");
        const execution_child = get_item("OKR Workspace", "Execution");

        if (execution_child.length && root_item.length) {
            root_item.remove();
            return;
        }

        if (!root_item.length || !execution_item.length) return;

        const child_container = execution_item
            .find("> .sidebar-child-item, > .sidebar-group-items, > .sidebar-items, > .collapse, > ul")
            .first();

        if (!child_container.length) return;

        root_item.attr("item-parent", "Execution");
        child_container.prepend(root_item);
    }
    function update_custom_page_links() {
        [...CUSTOM_PAGE_ROUTES, ...DIRECT_LIST_ROUTES].forEach(({ name, parent, path }) => {
            get_item(name, parent).find("> .desk-sidebar-item > .item-anchor").attr("href", path);
        });
    }

    function remove_leaf_controls() {
        ["OKR Action Item", "OKR Check In", "Check-In"].forEach((name) => {
            get_item(name, "OKR Workspace")
                .find("> .desk-sidebar-item > .sidebar-item-control")
                .remove();
        });
    }

    function bind_okr_sidebar() {
        patch_router();
        OKR_GROUPS.forEach(bind_group_toggle);
        normalize_workspace_position();
        update_custom_page_links();
        remove_leaf_controls();
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
            window.location.assign(route.path);
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
