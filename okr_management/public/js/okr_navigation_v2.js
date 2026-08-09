(() => {
    const is_administrator = () => frappe.session.user === "Administrator";

    const destination_for = (name) => {
        const routes = {
            "OKR Admin Workspace": is_administrator() ? "/app/admin-workspace" : "/app/okr-workspace",
            "Plan": is_administrator() ? "/app/okr-plan" : "/app/okr-workspace",
            "OKR Workspace": is_administrator() ? "/app/admin-workspace" : "/app/okr-workspace",
            "Objective": "/app/okr-objective",
            "Key Result": "/app/okr-key-result",
            "Action Item": "/app/okr-action-item",
            "Check-In": "/app/okr-check-in",
        };
        return routes[name];
    };

    const legacy_routes = {
        "/app/okr-admin-workspace": "/app/admin-workspace",
        "/app/plan": "/app/okr-plan",
        "/app/objective": "/app/okr-objective",
        "/app/key-result": "/app/okr-key-result",
        "/app/action-item": "/app/okr-action-item",
        "/app/check-in": "/app/okr-check-in",
    };

    function redirect_legacy_route() {
        let destination = legacy_routes[window.location.pathname];
        if (!is_administrator() && window.location.pathname === "/app/admin-workspace") {
            destination = "/app/okr-workspace";
        }
        if (!is_administrator() && window.location.pathname === "/app/okr-plan") {
            destination = "/app/okr-workspace";
        }
        if (destination && destination !== window.location.pathname) {
            window.location.replace(destination);
            return true;
        }
        return false;
    }

    function rewrite_sidebar_links() {
        document.querySelectorAll(".sidebar-item-container").forEach((item) => {
            const destination = destination_for(item.getAttribute("item-name"));
            if (!destination) return;
            const anchor = item.querySelector(":scope > .desk-sidebar-item > .item-anchor");
            if (anchor) anchor.setAttribute("href", destination);
        });
    }

    document.addEventListener("click", (event) => {
        const anchor = event.target.closest && event.target.closest(".desk-sidebar-item > .item-anchor");
        const item = anchor && anchor.closest(".sidebar-item-container");
        if (!item) return;
        const destination = destination_for(item.getAttribute("item-name"));
        if (!destination) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.location.assign(destination);
    }, true);

    if (redirect_legacy_route()) return;

    const bind = () => {
        rewrite_sidebar_links();
        redirect_legacy_route();
    };
    new MutationObserver(bind).observe(document.documentElement, {childList: true, subtree: true});
    document.addEventListener("DOMContentLoaded", bind);
    window.setTimeout(bind, 0);
    window.setTimeout(bind, 500);
})();
