frappe.ui.form.on("OKR Objective", {
	setup(frm) {
		frm.set_query("parent_plan", () => ({
			query: "okr_management.okr_management.doctype.okr_objective.okr_objective.search_available_plans",
			filters: { status: ["in", ["Draft", "Active"]] },
		}));
		frm.set_query("group", () => ({
			filters: { company: frm.doc.company, disabled: 0 },
		}));
		const group_field = frappe.meta.get_docfield("OKR Objective", "group", frm.doc.name);
		if (group_field) group_field.only_select = 1;
	},
	onload(frm) {},
	onload_post_render(frm) {
		if (frm.doc.parent_plan) load_plan_context(frm, false);
		else render_plan_context_preview(frm, {});
		layout_summary_fields(frm);
		layout_timeline_fields(frm);
		match_description_heights(frm);
		setup_auto_growing_title(frm);
	},
	refresh(frm) {
		configure_objective_form(frm);
		frm.doc.parent_plan ? load_plan_context(frm, false) : clear_plan_context(frm);
		layout_summary_fields(frm);
		layout_timeline_fields(frm);
		match_description_heights(frm);
		setup_auto_growing_title(frm);
		hide_destructive_objective_actions(frm);
	},
	objective_title(frm) {
		resize_objective_title(frm);
	},
	parent_plan(frm) {
		load_plan_context(frm, true);
	},

	status(frm) {
		configure_objective_form(frm);
	},
	validate(frm) {
		if (frm.is_new() && !frm.doc.group) frappe.throw(__("Group is required."));
	},
});

function hide_destructive_objective_actions(frm) {
	[__("Archive"), __("Delete"), __("Remove")].forEach((label) => {
		frm.page.remove_menu_item(label);
	});
}

function configure_objective_status(frm, plan_status) {
	const statuses = ["Draft", "Active", "On Hold", "Completed", "Closed"];
	frm.set_df_property("status", "options", statuses.join("\n"));
	if (!frm.is_new()) return;
	const required_status = plan_status === "Active" ? "Active" : "Draft";
	if (frm.doc.status !== required_status) frm.set_value("status", required_status);
}

function setup_auto_growing_title(frm) {
	const input = frm.fields_dict.objective_title?.$wrapper?.find("textarea").first();
	if (!input?.length) return;

	input.off("input.okr-title-resize").on("input.okr-title-resize", () => {
		resize_objective_title(frm);
	});
	resize_objective_title(frm);
}

function resize_objective_title(frm) {
	const input = frm.fields_dict.objective_title?.$wrapper?.find("textarea").first();
	if (!input?.length) return;

	const textarea = input[0];
	textarea.style.setProperty("height", "auto", "important");
	textarea.style.setProperty("min-height", "38px", "important");
	textarea.style.setProperty("max-height", "none", "important");
	textarea.style.setProperty("overflow-y", "hidden", "important");
	textarea.style.setProperty("resize", "none", "important");
	textarea.style.setProperty("height", Math.max(38, textarea.scrollHeight) + "px", "important");
}

function match_description_heights(frm) {
	const wrapper = frm.fields_dict.description?.$wrapper;
	if (!wrapper?.length) return;

	const input = wrapper.find("textarea").first();
	if (!input.length) return;
	input[0].style.setProperty("height", "84px", "important");
	input[0].style.setProperty("min-height", "84px", "important");
	input[0].style.setProperty("max-height", "none", "important");
	input[0].style.setProperty("resize", "vertical", "important");
}
function configure_objective_form(frm) {
	["plan_name", "plan_description", "company", "financial_year", "plan_owner"].forEach(
		(fieldname) => frm.set_df_property(fieldname, "read_only", 1)
	);

	frm.set_df_property("context_preview_html", "label", __("Context and Preview of Plan"));
	frm.toggle_display("context_preview_html", 1);
	frm.toggle_display("plan_team_preview", 0);
	[
		"plan_name",
		"plan_description",
		"company",
		"financial_year",
		"plan_owner",
		"timeline_preview",
		"plan_team_preview",
	].forEach((fieldname) => frm.set_df_property(fieldname, "hidden", 1));

	const is_closed = frm.doc.status === "Closed";
	frm.set_df_property("parent_plan", "hidden", 0);
	frm.set_df_property("parent_plan", "reqd", 1);
	frm.set_df_property("parent_plan", "read_only", !frm.is_new());
	frm.toggle_display("parent_plan", true);
	frm.set_df_property("level", "hidden", 1);
	frm.set_df_property("level", "reqd", 0);
	frm.set_df_property("level", "options", "Department");
	frm.toggle_display("level", false);
	frm.refresh_field("parent_plan");
	frm.refresh_field("level");

	[
		"objective_title",
		"description",
		"group",
		"priority",
		"status",
		"start_date",
		"end_date",
	].forEach((fieldname) => {
		frm.set_df_property(fieldname, "hidden", 0);
		frm.set_df_property(fieldname, "read_only", is_closed ? 1 : 0);
		frm.toggle_display(fieldname, true);
		frm.toggle_enable(fieldname, !is_closed);
		frm.fields_dict[fieldname]?.$wrapper?.show();
		frm.refresh_field(fieldname);
	});
	frm.set_df_property("department", "hidden", 1);
	frm.toggle_display("department", false);
	frm.set_df_property("owner_user", "hidden", 1);
	frm.toggle_display("owner_user", false);
	frm.set_df_property("technical_section", "hidden", 1);
	frm.toggle_display("technical_section", false);
	if (!is_closed) {
		frm.enable_save();
	}
	setTimeout(() => {
		match_description_heights(frm);
		setup_auto_growing_title(frm);
	}, 0);

	if (
		window.okr_management &&
		window.okr_management.ui &&
		window.okr_management.ui.apply_context_panel_style
	) {
		window.okr_management.ui.apply_context_panel_style(frm);
	}
}

function load_plan_context(frm, auto_populate_dates = false) {
	if (!frm.doc.parent_plan) {
		clear_plan_context(frm);
		return;
	}

	const selected_plan = frm.doc.parent_plan;
	frappe
		.call({
			method: "okr_management.okr_management.doctype.okr_plan.okr_plan.get_plan_context",
			args: { plan_name: selected_plan },
		})
		.then((response) => {
			if (frm.doc.parent_plan !== selected_plan) return;

			const context = response.message || {};
			frm._plan_context = context;
			configure_objective_status(frm, context.status);
			show_selected_plan_name(frm, selected_plan, context.plan_name);
			const values = {
				plan_name: context.plan_name || "",
				plan_description: context.description || "",
				company: context.company || "",
				plan_owner: context.plan_owner || "",
			};

			if (auto_populate_dates || (frm.is_new() && !frm.doc.start_date && !frm.doc.end_date)) {
				const def_start = context.default_start_date || context.start_date || "";
				const def_end = context.default_end_date || context.end_date || "";
				if (def_start) values.start_date = def_start;
				if (def_end) values.end_date = def_end;
			}

			// Financial Year is derived from the selected Plan and populated again
			// server-side during validation. Avoid client Link permission validation for
			// this hidden context field; OKR Users do not need Fiscal Year access.
			frm.doc.financial_year = context.financial_year || "";
			frm.refresh_field("financial_year");
			frm.set_value(values);
			render_plan_context_preview(frm, context);
			match_description_heights(frm);
		});
}

function show_selected_plan_name(frm, plan_code, plan_name) {
	if (!plan_code || !plan_name) return;

	const control = frm.fields_dict.parent_plan;
	if (!control) return;

	frappe.utils.add_link_title("OKR Plan", plan_code, plan_name);
	const apply_title = () => {
		if (frm.doc.parent_plan !== plan_code || !control.$input?.length) return;
		control.title_value_map = control.title_value_map || {};
		control.title_value_map[plan_name] = plan_code;
		control.set_input_value(plan_name);
	};

	apply_title();
	setTimeout(apply_title, 100);
}

function clear_plan_context(frm) {
	frm._plan_context = null;
	configure_objective_status(frm, "");
	[
		"plan_name",
		"plan_description",
		"company",
		"financial_year",
		"plan_owner",
		"start_date",
		"end_date",
	].forEach((fieldname) => frm.set_value(fieldname, ""));
	render_plan_context_preview(frm, {});
}

function render_plan_context_preview(frm, context) {
	const field = frm.fields_dict.context_preview_html;
	if (!field || !field.$wrapper) return;

	const ctx = context || {};
	let timeline_value = __("Select a Plan to preview its timeline.");
	const start_date = ctx.start_date || frm.doc.start_date;
	const end_date = ctx.end_date || frm.doc.end_date;
	if (start_date && end_date) {
		timeline_value =
			frappe.datetime.str_to_user(start_date) +
			" → " +
			frappe.datetime.str_to_user(end_date);
		timeline_value +=
			" • " +
			__("{0} Days", [frappe.datetime.get_day_diff(end_date, start_date) + 1]).replace(
				" ",
				"\u00a0"
			);
	}

	const team_rows = (ctx.members || [])
		.map((member) => {
			const name = frappe.utils.escape_html(member.full_name || member.user || "");
			const role = frappe.utils.escape_html(
				member.role === "Admin" ? __("Plan Coordinator") : member.role || ""
			);
			return (
				'<li style="margin:0 0 6px;">' +
				name +
				(role
					? ' <span style="color:var(--text-muted); font-size:11px;">(' +
					  role +
					  ")</span>"
					: "") +
				"</li>"
			);
		})
		.join("");

	const team_html = team_rows
		? '<ul style="margin:0;padding-left:18px;">' + team_rows + "</ul>"
		: '<span style="color:var(--text-muted);">' + __("No Plan Team members") + "</span>";

	const icons = {
		tag: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
		calendar:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
		building:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
		trending:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
		clock: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
		notes: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
		timer: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
		team: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
	};

	render_preview_cards(
		field,
		[
			{ icon: icons.tag, label: __("Plan Name"), value: ctx.plan_name || frm.doc.plan_name },
			{
				icon: icons.calendar,
				label: __("Financial Year"),
				value: ctx.financial_year || frm.doc.financial_year,
			},
			{
				icon: icons.building,
				label: __("Organization"),
				value: ctx.company || frm.doc.company,
			},
			{ icon: icons.trending, label: __("Status"), value: ctx.status || frm.doc.status },
			{
				icon: icons.timer,
				label: __("Sprint Frequency"),
				value: ctx.sprint_frequency || frm.doc.sprint_frequency,
			},
			{ icon: icons.clock, label: __("Timeline"), value: timeline_value },
			{
				icon: icons.notes,
				label: __("Description"),
				value: ctx.description || frm.doc.plan_description,
				wide: true,
			},
			{ icon: icons.team, label: __("Plan Team"), html: team_html, wide: true },
		],
		__("No plan context available."),
		__("Context and Preview of Plan")
	);
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
function layout_summary_fields(frm) {
	const fields = ["group", "priority", "status"]
		.map((fieldname) => frm.fields_dict[fieldname]?.$wrapper)
		.filter(Boolean);
	if (fields.length !== 3) return;

	let row = fields[0].parent(".okr-objective-summary-row");
	if (!row.length) {
		row = $('<div class="okr-objective-summary-row"></div>');
		fields[0].before(row);
		fields.forEach((field) => row.append(field));
	}

	row.css({
		display: "grid",
		"grid-template-columns": "repeat(auto-fit, minmax(160px, 1fr))",
		gap: "12px",
		width: "100%",
		"align-items": "start",
	});
	fields.forEach((field) => field.css({ "min-width": "0", margin: "0" }));
}
function layout_timeline_fields(frm) {
	const fields = ["start_date", "end_date"]
		.map((fieldname) => frm.fields_dict[fieldname]?.$wrapper)
		.filter(Boolean);
	if (fields.length !== 2) return;

	let row = fields[0].parent(".okr-objective-timeline-row");
	if (!row.length) {
		row = $('<div class="okr-objective-timeline-row"></div>');
		fields[0].before(row);
		fields.forEach((field) => row.append(field));
	}

	row.css({
		display: "grid",
		"grid-template-columns": "repeat(2, minmax(0, 1fr))",
		gap: "12px",
		width: "100%",
		"align-items": "start",
		"margin-top": "14px",
	});
	fields.forEach((field) => field.css({ "min-width": "0", margin: "0" }));
}
