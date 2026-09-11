frappe.ui.form.on("OKR Key Result", {
	setup(frm) {
		set_measurement_type_options(frm);
	},
	onload_post_render(frm) {
		if (frm.doc.objective) {
			populate_objective_context(frm);
		} else render_key_result_context_preview(frm, {});
		match_description_heights(frm);
		setup_auto_growing_key_result_title(frm);
		hide_section_headers(frm);
		setup_realtime_inputs(frm);
		sync_key_result_owner(frm);
	},
	refresh(frm) {
		apply_key_result_ui(frm);
		update_objective_date_range(frm);
		if (frm.doc.objective) populate_objective_context(frm);
		else render_key_result_context_preview(frm, {});
		match_description_heights(frm);
		setup_auto_growing_key_result_title(frm);
		hide_section_headers(frm);
		calculate_target_progress(frm);
		setup_realtime_inputs(frm);
		sync_key_result_owner(frm);
		setup_action_item_connection_route(frm);
	},
	objective(frm) {
		populate_objective_context(frm);
	},
	assignee(frm) {
		sync_key_result_owner(frm);
	},
	calculation_mode(frm) {
		apply_key_result_ui(frm);
	},
	metric_type(frm) {
		handle_metric_type_change(frm);
		apply_key_result_ui(frm);
	},
	currency(frm) {
		apply_key_result_ui(frm);
	},
	metric_direction(frm) {
		calculate_target_progress(frm);
	},
	baseline_value(frm) {
		initialize_new_current_from_baseline(frm);
		calculate_target_progress(frm);
	},
	target_value(frm) {
		calculate_target_progress(frm);
	},
	current_value(frm) {
		if (!frm.__setting_initial_current) frm.__current_value_was_edited = true;
		calculate_target_progress(frm);
	},
});

function setup_action_item_connection_route(frm) {
	if (frm.is_new()) return;
	setTimeout(() => {
		const link = frm.dashboard?.transactions_area?.find(
			'.document-link[data-doctype="OKR Action Item"] .badge-link'
		);
		if (!link?.length) return;
		link.off("click").on("click.okr-new-action", (event) => {
			event.preventDefault();
			event.stopImmediatePropagation();
			frappe.route_options = { parent_key_result: frm.doc.name };
			frappe.new_doc("OKR Action Item");
		});
	}, 0);
}

function set_measurement_type_options(frm) {
	frm.set_df_property("metric_type", "options", [
		{ label: __("Percentage"), value: "Percentage" },
		{ label: __("Number"), value: "Number" },
		{ label: __("Amount"), value: "Currency" },
	]);
}

function sync_key_result_owner(frm) {
	if (frm.doc.assignee && frm.doc.owner_user !== frm.doc.assignee) {
		frm.set_value("owner_user", frm.doc.assignee);
	}
}

const INHERITED_FIELDS = [
	"parent_plan",
	"objective_title",
	"company",
	"financial_year",
	"group",
	"department",
	"plan_owner",
	"objective_owner",
	"objective_level",
	"date_range",
];

function populate_objective_context(frm) {
	if (!frm.doc.objective) {
		clear_objective_context(frm);
		return;
	}

	frappe.db
		.get_value("OKR Objective", frm.doc.objective, [
			"parent_plan",
			"objective_title",
			"company",
			"financial_year",
			"group",
			"department",
			"plan_owner",
			"owner_user",
			"level",
			"description",
			"start_date",
			"end_date",
		])
		.then((r) => {
			const objective = r.message || {};
			frm._objective_description = objective.description || "";
			if (!objective.parent_plan) return objective;
			return frappe
				.call({
					method: "okr_management.okr_management.doctype.okr_plan.okr_plan.get_plan_context",
					args: { plan_name: objective.parent_plan },
				})
				.then((plan_response) => {
					const plan = plan_response.message || {};
					frm._parent_plan_title = plan.plan_name || objective.parent_plan || "";
					const objective_start = objective.start_date || plan.start_date || "";
					const objective_end = objective.end_date || plan.end_date || "";
					const values = {
						parent_plan: objective.parent_plan || "",
						objective_title: objective.objective_title || "",
						company: objective.company || "",
						department: objective.department || "",
						plan_owner: objective.plan_owner || "",
						objective_owner: objective.owner_user || "",
						objective_level: objective.level || "",
					};
					if (!frm.doc.end_date) {
						values.end_date = objective_end;
					}
					if (!frm.doc.start_date) {
						values.start_date = objective_start;
					}
					frm.doc.financial_year = plan.financial_year || objective.financial_year || "";
					frm.doc.group = objective.group || "";
					frm.refresh_field("financial_year");
					frm.set_value(values);
					update_objective_date_range(frm, objective_start, objective_end);
					frm._objective_context = {
						...objective,
						plan_name: frm._parent_plan_title,
						start_date: objective_start,
						end_date: objective_end,
					};
					render_key_result_context_preview(frm, frm._objective_context);
				});
		});
}

function clear_objective_context(frm) {
	frm._parent_plan_title = "";
	frm.doc.group = "";
	const values = {};
	INHERITED_FIELDS.forEach((fieldname) => {
		if (fieldname !== "group") {
			values[fieldname] = "";
		}
	});
	frm.set_value(values);
	render_key_result_context_preview(frm, {});
}

function update_objective_date_range(frm, start_date, end_date) {
	const start = start_date || frm.doc.start_date;
	const end = end_date || frm.doc.end_date;
	if (
		start === undefined ||
		start === null ||
		start === "" ||
		end === undefined ||
		end === null ||
		end === ""
	) {
		frm.set_value("date_range", "");
		render_key_result_context_preview(frm);
		return;
	}

	const days = moment(end).diff(moment(start), "days") + 1;
	const label =
		frappe.datetime.str_to_user(start) +
		" to " +
		frappe.datetime.str_to_user(end) +
		(days > 0 ? " (" + days + " days)" : "");
	frm.set_value("date_range", label);
	render_key_result_context_preview(frm);
}

function apply_key_result_ui(frm) {
	frm.set_df_property("naming_series", "hidden", 1);
	frm.set_df_property("kr_details_section", "label", "");
	frm.set_df_property("kr_details_col_break", "label", "");
	frm.set_df_property(
		"context_preview_html",
		"label",
		__("Context and Preview of Plan and Objective")
	);
	frm.toggle_display("context_preview_html", 1);

	INHERITED_FIELDS.forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", 1);
	});
	[
		"parent_plan",
		"objective_title",
		"company",
		"financial_year",
		"group",
		"department",
		"date_range",
		"owner_user",
		"ownership_section",
		"ownership_col_break",
		"ownership_status_col_break",
		"plan_owner",
		"objective_owner",
		"objective_level",
		"context_preview_heading",
	].forEach((fieldname) => {
		frm.set_df_property(fieldname, "hidden", 1);
	});

	frm.set_df_property("start_date", "hidden", 1);
	frm.set_df_property("start_date", "read_only", 0);
	frm.set_df_property("start_date", "reqd", 0);
	frm.set_df_property("end_date", "hidden", 0);
	frm.set_df_property("end_date", "read_only", 0);
	frm.set_df_property("end_date", "reqd", 1);

	["target_progress", "score", "action_item_count", "checkin_count"].forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", 1);
	});
	frm.set_df_property("summary_sidebar_section", "hidden", 1);
	frm.set_df_property("target_progress", "hidden", 1);

	frm.set_df_property("current_value", "hidden", 0);
	frm.set_df_property("current_value", "read_only", 0);
	frm.toggle_display("currency", 0);

	const metric_type = frm.doc.metric_type;
	frm.toggle_reqd("target_value", metric_type === "Percentage");
	frm.set_df_property(
		"unit_of_measure",
		"placeholder",
		"e.g., Customers, Leads, Orders, Hours, Tasks, Bottles, Calls"
	);

	frm.toggle_display("unit_of_measure", 0);
	frm.set_df_property("unit_of_measure", "read_only", 1);

	let baseline_label = __("Starting Value (Current)");
	let target_label = __("Target to Achieve");
	let current_label = __("Current Value");

	if (metric_type === "Percentage") {
		baseline_label = __("Starting Percentage (%)");
		target_label = __("Target Percentage (%)");
		current_label = __("Current Percentage (%)");
		if (frm.doc.unit_of_measure != "%") {
			frm.set_value("unit_of_measure", "%");
		}
	} else if (metric_type === "Number") {
		baseline_label = __("Starting Value");
		target_label = __("Target Value");
		current_label = __("Current Value");
		if (frm.doc.unit_of_measure === "%") {
			frm.set_value("unit_of_measure", "");
		}
	} else if (metric_type === "Currency") {
		baseline_label = __("Starting Amount");
		const currency = frm.doc.currency || frappe.defaults.get_default("currency") || "";
		baseline_label = currency
			? __("Starting Amount ({0})", [currency])
			: __("Starting Amount");
		target_label = currency ? __("Target Amount ({0})", [currency]) : __("Target Amount");
		current_label = currency ? __("Current Amount ({0})", [currency]) : __("Current Amount");
	}

	frm.set_df_property("baseline_value", "label", baseline_label);
	frm.set_df_property("target_value", "label", target_label);
	frm.set_df_property("current_value", "label", current_label);
	frm.set_df_property("current_value", "description", measurement_guidance(frm));
	render_measurement_guidance(frm);

	if (
		window.okr_management &&
		window.okr_management.ui &&
		window.okr_management.ui.apply_context_panel_style
	) {
		window.okr_management.ui.apply_context_panel_style(frm);
	}
}


function measurement_guidance(frm) {
	const metric_type = frm.doc.metric_type || "Percentage";
	if (metric_type === "Percentage") {
		return __("Enter the actual percentage reached, for example 40 for 40%.");
	}
	if (metric_type === "Number") {
		return __("Enter the actual result, not completion %. Example: Start 2, Target 10, Current 4.");
	}
	if (metric_type === "Currency") {
		const currency = frm.doc.currency || frappe.defaults.get_default("currency") || "₹";
		return __("Enter the actual amount reached, for example {0}4,00,000.", [currency === "INR" ? "₹" : currency + " "]);
	}
	if (metric_type === "Boolean") {
		return __("Enter 0 for Not Achieved or 1 for Achieved.");
	}
	return __("Enter the actual measured value, not the completion percentage.");
}

function render_measurement_guidance(frm, preview_progress = null) {
	const field = frm.fields_dict.current_value;
	if (!field || !field.$wrapper) return;

	const source_progress = preview_progress === null ? frm.doc.target_progress || 0 : preview_progress;
	const progress = Math.min(100, Math.max(0, flt(source_progress, 2)));
	const progress_text = Number.isInteger(progress) ? String(progress) : String(flt(progress, 2));
	field.$wrapper.find(".okr-measurement-info").remove();
	field.$wrapper.find(".okr-live-completion").remove();
	const preview = $(`
		<div class="okr-live-completion" style="margin-top:10px;padding:10px 12px;border:1px solid var(--border-color);border-radius:8px;background:var(--subtle-fg);">
			<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:7px;font-size:12px;">
				<span style="color:var(--text-muted);font-weight:600;">${__("Calculated completion")}</span>
				<strong style="color:var(--text-color);">${progress_text}%</strong>
			</div>
			<div style="height:6px;border-radius:999px;background:var(--gray-200);overflow:hidden;">
				<div style="height:100%;width:${progress}%;border-radius:inherit;background:var(--primary);transition:width .2s ease;"></div>
			</div>
		</div>
	`);
	const $description = field.$wrapper.find(".help-box").last();
	if ($description.length) preview.insertAfter($description);
	else field.$wrapper.append(preview);
}

function handle_metric_type_change(frm) {
	const metric_type = frm.doc.metric_type;
	if (metric_type === "Percentage") {
		if (
			frm.doc.target_value === undefined ||
			frm.doc.target_value === null ||
			frm.doc.target_value === 0
		) {
			frm.set_value("target_value", 100);
		}
		if (!frm.doc.unit_of_measure || frm.doc.unit_of_measure === "") {
			frm.set_value("unit_of_measure", "%");
		}
	} else if (metric_type === "Boolean") {
		if (frm.doc.target_value !== 0 && frm.doc.target_value !== 1) {
			frm.set_value("target_value", 1);
		}
		frm.set_value("unit_of_measure", "");
	} else if (metric_type === "Number") {
		if (frm.doc.target_value === 100 || frm.doc.target_value === 1) {
			frm.set_value("target_value", "");
		}
		if (frm.doc.unit_of_measure === "%") {
			frm.set_value("unit_of_measure", "");
		}
	} else if (metric_type === "Currency") {
		if (frm.doc.target_value === 100 || frm.doc.target_value === 1) {
			frm.set_value("target_value", "");
		}
		frm.set_value("unit_of_measure", "");
	}
}

function render_key_result_context_preview(frm, context) {
	const field = frm.fields_dict.context_preview_html;
	if (!field || !field.$wrapper) return;

	const ctx = context || {};
	let timeline_value = __("Select an Objective to preview the date range.");
	const start_date = ctx.start_date || frm.doc.start_date;
	const end_date = ctx.end_date || frm.doc.end_date;
	if (frm.doc.date_range) {
		timeline_value = frm.doc.date_range;
	} else if (start_date && end_date) {
		timeline_value =
			frappe.datetime.str_to_user(start_date) +
			" → " +
			frappe.datetime.str_to_user(end_date);
	}

	const icons = {
		flag: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
		plan: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
		building:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
		calendar:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
		group: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
		clock: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
	};

	const obj_desc = ctx.description || frm._objective_description || "";
	render_preview_cards(
		field,
		[
			{
				icon: icons.flag,
				label: __("Objective"),
				value: ctx.objective_title || frm.doc.objective_title || frm.doc.objective,
			},
			{
				icon: icons.plan,
				label: __("Plan"),
				value:
					ctx.plan_name ||
					frm._parent_plan_title ||
					ctx.parent_plan ||
					frm.doc.parent_plan,
			},
			{
				icon: icons.building,
				label: __("Organization"),
				value: ctx.company || frm.doc.company,
			},
			{
				icon: icons.calendar,
				label: __("Financial Year"),
				value: ctx.financial_year || frm.doc.financial_year,
			},
			{
				icon: icons.group,
				label: __("Group"),
				value: ctx.group || frm.doc.group,
				wide: true,
			},
			{ icon: icons.clock, label: __("Timeline"), value: timeline_value, wide: true },
			{ icon: icons.plan, label: __("Objective Description"), value: obj_desc, wide: true },
		],
		__("Select an Objective to preview its context.")
	);
}

function render_preview_cards(field, cards, empty_message, title) {
	if (!field || !field.$wrapper) return;
	const visible_cards = cards || [];
	const escape_html = (val) => frappe.utils.escape_html(String(val ?? "—"));
	const header_title = title || __("Context and Preview of Plan and Objective");

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

function setup_auto_growing_key_result_title(frm) {
	const input = frm.fields_dict.key_result_title?.$wrapper?.find("textarea").first();
	if (!input?.length) return;
	input.off("input.okr-title-resize").on("input.okr-title-resize", () => resize_key_result_title(frm));
	resize_key_result_title(frm);
}

function resize_key_result_title(frm) {
	const input = frm.fields_dict.key_result_title?.$wrapper?.find("textarea").first();
	if (!input?.length) return;
	const textarea = input[0];
	textarea.style.setProperty("height", "auto", "important");
	textarea.style.setProperty("min-height", "38px", "important");
	textarea.style.setProperty("max-height", "none", "important");
	textarea.style.setProperty("overflow-y", "hidden", "important");
	textarea.style.setProperty("resize", "none", "important");
	textarea.style.setProperty("height", Math.max(38, textarea.scrollHeight) + "px", "important");
}

function initialize_new_current_from_baseline(frm) {
	if (!frm.is_new() || frm.__current_value_was_edited) return;
	frm.__setting_initial_current = true;
	frm.set_value("current_value", flt(frm.doc.baseline_value || 0)).then(() => {
		frm.__setting_initial_current = false;
	});
}

function match_description_heights(frm) {
	const field = frm.fields_dict.description;
	if (!field || !field.$wrapper) return;
	field.$wrapper.find("textarea").css({
		height: "74px",
		"min-height": "74px",
		"max-height": "74px",
	});
}

function hide_section_headers(frm) {
	["kr_details_section", "inherited_context_section"].forEach((fieldname) => {
		const section = frm.fields_dict[fieldname];
		if (section && section.wrapper) {
			section.wrapper.find(".section-head").hide();
		}
	});
}

function calculate_target_progress(frm) {
	const baseline = flt(frm.doc.baseline_value || 0);
	const target = flt(frm.doc.target_value || 0);
	const current = flt(frm.doc.current_value || 0);
	const direction = frm.doc.metric_direction || "Increase";
	const metric_type = frm.doc.metric_type || "Percentage";

	let progress = 0;

	if (metric_type === "Boolean") {
		progress = current >= target ? 100 : 0;
	} else {
		if (direction === "Decrease") {
			if (target === baseline || current < target) {
				progress = 0;
			} else {
				progress = ((baseline - current) / (baseline - target)) * 100;
			}
		} else {
			if (target === baseline) {
				progress = 0;
			} else {
				progress = ((current - baseline) / (target - baseline)) * 100;
			}
		}
		progress = Math.min(100, Math.max(0, progress));
	}

	if (cint(frm.doc.action_item_count || 0) > 0) {
		// Preview the KR's own measurement live without replacing the persisted
		// Action Item average stored in target_progress.
		render_measurement_guidance(frm, progress);
		return;
	}
	frm.set_value("target_progress", flt(progress, 2));
	frm.set_value("score", flt(progress, 2));
	render_measurement_guidance(frm, progress);
}

function setup_realtime_inputs(frm) {
	if (frm.fields_dict.baseline_value && frm.fields_dict.baseline_value.$wrapper) {
		frm.fields_dict.baseline_value.$wrapper
			.off("input", "input")
			.on("input", "input", function () {
				const val = flt($(this).val());
				frm.doc.baseline_value = val;
				if (frm.is_new() && !frm.__current_value_was_edited) {
					frm.doc.current_value = val;
					frm.fields_dict.current_value?.set_input(val);
				}
				calculate_target_progress(frm);
			});
	}

	if (frm.fields_dict.target_value && frm.fields_dict.target_value.$wrapper) {
		frm.fields_dict.target_value.$wrapper
			.off("input", "input")
			.on("input", "input", function () {
				frm.doc.target_value = flt($(this).val());
				calculate_target_progress(frm);
			});
	}

	if (frm.fields_dict.current_value && frm.fields_dict.current_value.$wrapper) {
		frm.fields_dict.current_value.$wrapper
			.off("input.okr-measurement", "input")
			.on("input.okr-measurement", "input", function () {
				frm.__current_value_was_edited = true;
				frm.doc.current_value = flt($(this).val());
				calculate_target_progress(frm);
			});
	}
	calculate_target_progress(frm);
}
