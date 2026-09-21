frappe.provide("okr_management");

// Clear workspace selections created by the former Plan/OKR Planning titles.
try {
	const stale_okr_pages = new Set(["Plan", "OKR Planning"]);
	if (window.localStorage && stale_okr_pages.has(localStorage.getItem("current_page"))) {
		localStorage.removeItem("current_page");
		localStorage.removeItem("is_current_page_public");
	}
} catch (e) {
	// Ignore if localStorage is unavailable
}

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
				.text(
					`
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
                `
				)
				.appendTo(document.head);
		}
	},
};

window.okr_management.preview_attachment = function (file_url) {
	if (!file_url) return;
	let parsed;
	try {
		parsed = new URL(String(file_url), window.location.origin);
	} catch (error) {
		frappe.msgprint(__("Invalid attachment URL."));
		return;
	}
	if (
		parsed.origin !== window.location.origin ||
		!(parsed.pathname.startsWith("/files/") || parsed.pathname.startsWith("/private/files/"))
	) {
		frappe.msgprint(__("Only files uploaded to this site can be previewed."));
		return;
	}

	const preview_url = parsed.pathname + parsed.search;
	const safe_url = frappe.utils.escape_html(preview_url);
	const filename = decodeURIComponent(parsed.pathname.split("/").pop() || __("Attachment"));
	const safe_filename = frappe.utils.escape_html(filename);
	const extension = filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
	const image_types = new Set(["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"]);
	const spreadsheet_types = new Set(["xlsx", "xlsm", "xls", "csv"]);

	const show_preview = (preview_html) => {
		const dialog = new frappe.ui.Dialog({
			title: __("Attachment: {0}", [filename]),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "attachment_preview" }],
		});
		dialog.fields_dict.attachment_preview.$wrapper.html(preview_html);
		dialog.show();
		const download_html = `
			<a href="${safe_url}" download="${safe_filename}"
				class="btn btn-sm btn-primary okr-attachment-download" target="_blank" rel="noopener noreferrer"
				title="${__("Download attachment")}">
				${__("Download")}
			</a>`;
		const $modal_header = dialog.$wrapper.find(".modal-header");
		const $modal_actions = $modal_header.find(".modal-actions");
		$modal_header.css({
			display: "flex",
			alignItems: "center",
			justifyContent: "space-between",
			flexWrap: "nowrap",
			gap: "16px",
		});
		$modal_header.find(".modal-title").css({
			margin: 0,
			minWidth: 0,
			lineHeight: "1.35",
			wordBreak: "break-word",
		});
		if ($modal_actions.length) {
			$modal_actions.prepend($(download_html)).css({
				display: "flex",
				flexDirection: "row",
				alignItems: "center",
				justifyContent: "flex-end",
				flexWrap: "nowrap",
				gap: "8px",
				marginLeft: "auto",
				flexShrink: 0,
			});
			$modal_actions.children().css({ margin: 0, flexShrink: 0 });
			$modal_actions.find(".okr-attachment-download").css({
				display: "inline-flex",
				alignItems: "center",
				justifyContent: "center",
				padding: "6px 14px",
			});
		} else {
			$modal_header.append($(download_html));
		}
	};

	if (spreadsheet_types.has(extension)) {
		frappe.call({
			method: "okr_management.attachment_preview.get_spreadsheet_preview",
			args: { file_url: preview_url },
			freeze: true,
			freeze_message: __("Preparing spreadsheet preview..."),
			callback: (r) => {
				if (r.exc) return;
				const result = r.message || {};
				const rows = result.rows || [];
				if (!rows.length) {
					show_preview(`<div class="text-muted" style="padding:32px;text-align:center">${__("This spreadsheet is empty.")}</div>`);
					return;
				}
				const width = Math.max(...rows.map((row) => row.length), 1);
				const table = rows.map((row, row_index) => {
					const tag = row_index === 0 ? "th" : "td";
					const cells = Array.from({ length: width }, (_, index) =>
						`<${tag} style="padding:7px 10px;border:1px solid var(--border-color);white-space:nowrap;text-align:left">${frappe.utils.escape_html(String(row[index] ?? ""))}</${tag}>`
					).join("");
					return `<tr>${cells}</tr>`;
				}).join("");
				const note = result.truncated
					? `<div class="text-muted" style="padding:8px 2px">${__("Preview limited to the first {0} rows and {1} columns. Download to view the complete spreadsheet.", [100, 30])}</div>`
					: "";
				show_preview(`${note}<div style="max-height:70vh;overflow:auto;border:1px solid var(--border-color);border-radius:8px"><table style="border-collapse:collapse;min-width:100%;background:var(--card-bg);color:var(--text-color)">${table}</table></div>`);
			},
		});
		return;
	}

	if (image_types.has(extension)) {
		show_preview(`<div style="display:flex;justify-content:center;max-height:72vh;overflow:auto;background:var(--subtle-fg);padding:12px;border-radius:8px"><img src="${safe_url}" alt="${safe_filename}" style="max-width:100%;height:auto;object-fit:contain"></div>`);
		return;
	}
	const embedded_url = extension === "pdf" ? safe_url + "#toolbar=0&navpanes=0" : safe_url;
	show_preview(`<iframe src="${embedded_url}" title="${safe_filename}" style="width:100%;height:72vh;border:1px solid var(--border-color);border-radius:8px;background:var(--card-bg)"></iframe>`);
};

(() => {
	// Keep permitted OKR DocTypes in Frappe's native route registry.
	const native_okr_routes = {
		// Backward-compatible aliases for bookmarks/history created by old workspace titles.
		"plan": "OKR Plan",
		"okr-planning": "OKR Plan",
		"okr-plan": "OKR Plan",
		"okr-objective": "OKR Objective",
		"okr-key-result": "OKR Key Result",
		"okr-action-item": "OKR Action Item",
		"okr-check-in": "OKR Check In",
	};
	Object.entries(native_okr_routes).forEach(([route, doctype]) => {
		frappe.router.routes[route] = { doctype };
	});

	function escape_html(value) {
		return frappe.utils.escape_html(String(value ?? "—"));
	}

	function render_preview_cards(field, cards, empty_message, title) {
		if (!field || !field.$wrapper) return;
		const visible_cards = cards || [];
		const escape_html = (val) => frappe.utils.escape_html(String(val ?? "—"));
		const header_title = title || __("Context and Preview");

		const card_html = visible_cards.length
			? visible_cards
					.map((card) => {
						if (!card) return "";
						const wide = Boolean(card.wide);
						let val = "—";
						if (
							card.value !== undefined &&
							card.value !== null &&
							String(card.value).trim() !== ""
						) {
							val = String(card.value);
						}
						const content =
							card.html ||
							'<div style="font-size:13px;font-weight:' +
								(wide ? "500" : "600") +
								";color:#1e293b;line-height:" +
								(wide ? "1.5" : "1.4") +
								';word-break:break-word;white-space:pre-wrap;">' +
								escape_html(val) +
								"</div>";
						return (
							'<div style="' +
							(wide ? "width:100%;" : "flex:1 1 45%;min-width:180px;") +
							"display:flex;align-items:" +
							(wide ? "flex-start" : "center") +
							';gap:10px;background:#f8f9fc;border:1px solid #e3e8ef;border-radius:10px;padding:10px 14px;">' +
							'<span style="font-size:18px;flex-shrink:0;margin-top:' +
							(wide ? "2px" : "0") +
							';color:#5b6b8a;display:flex;align-items:center;">' +
							(card.icon || "📌") +
							"</span>" +
							'<div style="min-width:0;">' +
							'<div style="font-size:10px;font-weight:600;color:#8d99ae;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;">' +
							escape_html(__(card.label || "")) +
							"</div>" +
							content +
							"</div></div>"
						);
					})
					.join("")
			: '<div style="width:100%;padding:12px 14px;border:1px dashed #d6dbe6;border-radius:10px;color:var(--text-muted);background:#fbfcfe;">' +
			  escape_html(empty_message || __("No context available.")) +
			  "</div>";

		const title_html =
			'<div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:10px;">' +
			escape_html(header_title) +
			"</div>";

		const cards_box_html =
			'<div style="border:1.5px solid #cbd5e0;border-radius:10px;background:#fafbff;padding:16px 18px;box-shadow:0 1px 6px rgba(0,0,0,0.06);display:flex;flex-wrap:wrap;gap:12px;">' +
			card_html +
			"</div>";

		field.$wrapper.prev(".okr-context-heading").remove();
		$(title_html).addClass("okr-context-heading").insertBefore(field.$wrapper);
		const full_html = cards_box_html;

		if (field.$wrapper && field.$wrapper[0]) {
			field.$wrapper[0].innerHTML = full_html;
		} else if (typeof field.set_value === "function") {
			field.set_value(full_html);
		}

		if (field.$wrapper) {
			field.$wrapper.css({
				border: "none",
				"border-radius": "0",
				background: "transparent",
				padding: "0",
				"box-shadow": "none",
				display: "block",
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
		const route = frappe.get_route ? frappe.get_route() || [] : [];
		const path = window.location.pathname.replace(/\/$/, "");
		return (
			(["Form", "List"].includes(route[0]) && OKR_DOCTYPES.has(route[1])) ||
			["/app/okr-workspace", "/app/admin-workspace", "/app/okr-admin-workspace"].includes(
				path
			)
		);
	}

	function refresh_okr_breadcrumbs() {
		if (!is_okr_route() || !frappe.breadcrumbs?.update) return;
		frappe.breadcrumbs.update();
	}

	function install_okr_breadcrumb_override() {
		if (!frappe.breadcrumbs?.set_workspace_breadcrumb) return false;
		if (frappe.breadcrumbs._okr_direct_breadcrumbs) return true;

		const original = frappe.breadcrumbs.set_workspace_breadcrumb.bind(frappe.breadcrumbs);
		frappe.breadcrumbs.set_workspace_breadcrumb = function (breadcrumbs) {
			if (
				breadcrumbs?.module === "OKR Management" ||
				OKR_DOCTYPES.has(breadcrumbs?.doctype)
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
		const route = frappe.get_route ? frappe.get_route() || [] : [];
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
	const OKR_DOCTYPES = new Set([
		"OKR Plan",
		"OKR Objective",
		"OKR Key Result",
		"OKR Action Item",
		"OKR Check In",
	]);

	["OKR Plan", "OKR Objective", "OKR Key Result", "OKR Action Item", "OKR Check In"].forEach(
		(doctype) => {
			frappe.ui.form.on(doctype, {
				dashboard_update(frm) {
					frm.$wrapper
						.find(".form-dashboard .open-notification")
						.addClass("hidden")
						.hide();

					// Ensure all document links show their count badge even if count is 0
					if (frm.dashboard_data?.count) {
						const all_links = [
							...(frm.dashboard_data.count.internal_links_found || []),
							...(frm.dashboard_data.count.external_links_found || []),
						];
						all_links.forEach((d) => {
							const $link = frm.$wrapper.find(`.form-dashboard .document-link[data-doctype="${d.doctype}"]`);
							if ($link.length) {
								let $count = $link.find(".count");
								if (!$count.length) {
									$count = $('<span class="count"></span>').prependTo($link.find(".document-link-badge"));
								}
								const count_num = cint(d.count);
								const count_text = count_num > 99 ? "99+" : `${count_num}`;
								$count.text(count_text).removeClass("hidden").show();
							}
						});
					}
				},
			});
		}
	);

	$(document).on("click", ".form-links .section-head", function () {
		const frm = window.cur_frm;
		if (frm && frm.dashboard && OKR_DOCTYPES.has(frm.doctype) && !frm.is_new()) {
			frm.dashboard._fetched_counts = false;
			if (typeof frm.dashboard.set_open_count === "function") {
				frm.dashboard.set_open_count();
			}
		}
	});
})();
// Respect custom workspace sidebar route mappings from get_workspace_sidebar_items.
(() => {
	function patch_workspace_sidebar_routes() {
		if (!frappe.views?.Workspace?.prototype?.sidebar_item_container) return false;
		if (frappe.views.Workspace.prototype._okr_route_patched) return true;

		const original_sidebar_item_container =
			frappe.views.Workspace.prototype.sidebar_item_container;

		frappe.views.Workspace.prototype.sidebar_item_container = function (item) {
			const $item = original_sidebar_item_container.call(this, item);
			if (item && item.route) {
				const href = item.route.startsWith("/") ? item.route : `/app/${item.route}`;
				$item.find("> .desk-sidebar-item > .item-anchor").attr("href", href);
			}
			return $item;
		};

		frappe.views.Workspace.prototype._okr_route_patched = true;
		return true;
	}

	function sync_rendered_sidebar_routes() {
		if (!frappe.workspace?.all_pages) return;
		const route_lookup = {};
		for (const page of frappe.workspace.all_pages) {
			if (page && page.title && page.route) {
				route_lookup[page.title] = page.route.startsWith("/")
					? page.route
					: `/app/${page.route}`;
			}
		}
		document.querySelectorAll(".sidebar-item-container[item-name]").forEach((el) => {
			const name = el.getAttribute("item-name");
			const target_href = route_lookup[name];
			if (target_href) {
				const anchor = el.querySelector(":scope > .desk-sidebar-item > a.item-anchor");
				if (anchor && anchor.getAttribute("href") !== target_href) {
					anchor.setAttribute("href", target_href);
				}
			}
		});
	}

	if (!patch_workspace_sidebar_routes()) {
		const timer = setInterval(() => {
			if (patch_workspace_sidebar_routes()) clearInterval(timer);
		}, 50);
	}

	$(document).on("page-change route-change", () => {
		setTimeout(sync_rendered_sidebar_routes, 50);
	});
	frappe.after_ajax && frappe.after_ajax(sync_rendered_sidebar_routes);
})();
