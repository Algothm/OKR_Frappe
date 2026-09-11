const okr_management = window.okr_management;

function setup_auto_growing_plan_title(frm, fieldname) {
	const input = frm.fields_dict[fieldname]?.$wrapper?.find("textarea").first();
	if (!input?.length) return;
	input.off("input.okr-title-resize").on("input.okr-title-resize", () => resize_auto_growing_plan_title(frm, fieldname));
	resize_auto_growing_plan_title(frm, fieldname);
}

function resize_auto_growing_plan_title(frm, fieldname) {
	const input = frm.fields_dict[fieldname]?.$wrapper?.find("textarea").first();
	if (!input?.length) return;
	const textarea = input[0];
	textarea.style.setProperty("height", "auto", "important");
	textarea.style.setProperty("min-height", "38px", "important");
	textarea.style.setProperty("max-height", "none", "important");
	textarea.style.setProperty("overflow-y", "hidden", "important");
	textarea.style.setProperty("resize", "none", "important");
	textarea.style.setProperty("height", Math.max(38, textarea.scrollHeight) + "px", "important");
}

frappe.dom.set_style(`
	.form-section[data-fieldname="plan_details_row_2"] .frappe-control[data-fieldname="description"] textarea {
		height: 194px !important;
		min-height: 194px !important;
		max-height: 194px !important;
		resize: none !important;
	}
`, "okr-plan-description-height-style");
frappe.ui.form.on("OKR Plan", {
	refresh(frm) {
		frm.set_df_property("naming_series", "hidden", 1);
		if (!frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_user_default("Company") || "");
		}
		if (!frm.doc.owner_user) {
			frm.set_value("owner_user", frappe.session.user);
		}
		if (frm.doc.owner_user && (!frm.doc.members || frm.doc.members.length === 0)) {
			frm.add_child("members", {
				member_user: frm.doc.owner_user,
				role: "Plan Coordinator",
			});
			frm.refresh_field("members");
		}
		apply_plan_locks(frm);
		fix_okr_plan_layout(frm);
		setup_auto_growing_plan_title(frm, "plan_name");
		match_plan_description_height(frm);
		style_add_member_button(frm);
		render_plan_context_preview(frm);
		schedule_description_height(frm);
		$(window).off("resize.okr_plan_desc").on("resize.okr_plan_desc", () => {
			match_plan_description_height(frm);
		});
		if (window.ResizeObserver && frm.fields_dict.sprint_frequency?.$wrapper?.length) {
			if (frm._sprint_observer) {
				frm._sprint_observer.disconnect();
			}
			frm._sprint_observer = new ResizeObserver(() => {
				match_plan_description_height(frm);
			});
			frm._sprint_observer.observe(frm.fields_dict.sprint_frequency.$wrapper[0]);
		}
		update_objective_connection_badge(frm);
		frm.$wrapper
			.off("click.okr_plan_connections", ".form-links .section-head")
			.on("click.okr_plan_connections", ".form-links .section-head", () => {
				setTimeout(() => {
					update_objective_connection_badge(frm);
				}, 50);
			});
	},
	dashboard_update(frm) {
		update_objective_connection_badge(frm);
	},
	status(frm) {
		if (frm.doc.status === "Active" && !frm.doc.planned_activation_date) {
			frm.set_value("planned_activation_date", frappe.datetime.get_today());
		}
		apply_plan_locks(frm);
		match_plan_description_height(frm);
		render_plan_context_preview(frm);
		schedule_description_height(frm);
	},
	financial_year(frm) {
		render_plan_context_preview(frm);
	},
	planned_activation_date(frm) {
		render_plan_context_preview(frm);
	},
	sprint_frequency(frm) {
		render_plan_context_preview(frm);
	},
	onload_post_render(frm) {
		fix_okr_plan_layout(frm);
		setup_auto_growing_plan_title(frm, "plan_name");
		match_plan_description_height(frm);
		style_add_member_button(frm);
		render_plan_context_preview(frm);
		schedule_description_height(frm);
	},
	members_add(frm) {
		style_add_member_button(frm);
	},
	members_remove(frm) {
		style_add_member_button(frm);
	},
	members_on_form_rendered(frm, cdt, cdn) {
		customize_row_editor(frm, cdt, cdn);
	},
});

function match_plan_description_height(frm) {
	const description = frm.fields_dict.description?.$wrapper;
	if (!description?.length) return;

	const textarea = description.find("textarea").first();
	if (!textarea.length) return;

	const sprint = frm.fields_dict.sprint_frequency?.$wrapper;
	if (!sprint?.length) return;

	const sprint_control = sprint.find("select:visible, input:visible, .control-input:visible").first();
	const target = sprint_control.length ? sprint_control[0] : sprint[0];

	let diff = 0;
	if (textarea.is(":visible") && $(target).is(":visible")) {
		const sprint_bottom = target.getBoundingClientRect().bottom;
		const textarea_top = textarea[0].getBoundingClientRect().top;
		diff = Math.round(sprint_bottom - textarea_top);
	}

	const final_height = 194;

	textarea[0].style.setProperty("height", `${final_height}px`, "important");
	textarea[0].style.setProperty("min-height", `${final_height}px`, "important");
	textarea[0].style.setProperty("max-height", `${final_height}px`, "important");
	textarea[0].style.setProperty("resize", "none", "important");
}

function apply_sprint_configuration_layout(frm) {
	// Standard columns layout is used
}

function render_plan_context_preview(frm) {
	const field = frm.fields_dict.context_preview_html;
	if (!field || !field.$wrapper) return;

	const timeline_value = frm.doc.financial_year || __("Select a Financial Year.");

	const icons = {
		tag: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
		calendar:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
		building:
			'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
		timer: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
		clock: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
		notes: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
	};

	okr_management.ui.render_preview_cards(
		field,
		[
			{ icon: icons.tag, label: __("Status"), value: frm.doc.status || __("Draft") },
			{ icon: icons.calendar, label: __("Financial Year"), value: frm.doc.financial_year },
			{
				icon: icons.clock,
				label: __("Activation Date"),
				value: frm.doc.planned_activation_date,
			},
			{ icon: icons.building, label: __("Organization"), value: frm.doc.company },
			{ icon: icons.timer, label: __("Sprint Frequency"), value: frm.doc.sprint_frequency },
			{ icon: icons.clock, label: __("Timeline"), value: timeline_value, wide: true },
			{
				icon: icons.notes,
				label: __("Description"),
				value: frm.doc.description,
				wide: true,
			},
		],
		__("No plan context available.")
	);
}

function style_add_member_button(frm) {
	let grid = frm.fields_dict["members"] && frm.fields_dict["members"].grid;
	if (grid && grid.wrapper) {
		let $btn = grid.wrapper.find(".grid-add-row");
		if ($btn.length > 0) {
			$btn.removeClass("btn-secondary btn-default btn-xs btn-sm").addClass(
				"btn-primary btn-sm"
			);
			const expected_text = __("Add Member");
			if (!$btn.text().includes(expected_text)) {
				let icon_html = "";
				if (frappe.utils && typeof frappe.utils.icon === "function") {
					icon_html = frappe.utils.icon("add", "xs") + " ";
				} else {
					icon_html = '<i class="fa fa-plus"></i> ';
				}
				$btn.html(icon_html + expected_text);
			}
			$btn.off("click").on("click.okr-plan-add-member", (event) => {
				event.preventDefault();
				event.stopImmediatePropagation();
				open_add_member_dialog(frm);
			});
		}
	}
}

function open_add_member_dialog(frm) {
	const role_options = (
		frappe.meta.get_docfield("OKR Plan Team Member", "role", frm.doc.name).options ||
		"Plan Coordinator"
	).split("\n");
	const dialog = new frappe.ui.Dialog({
		title: __("Add Member"),
		fields: [
			{
				fieldname: "member_user",
				fieldtype: "Link",
				label: __("User"),
				options: "User",
				reqd: 1,
			},
			{
				fieldname: "role",
				fieldtype: "Select",
				label: __("Role"),
				options: role_options.join("\n"),
				default: role_options[0],
				reqd: 1,
			},
		],
		primary_action_label: __("Save"),
		primary_action(values) {
			const already_added = (frm.doc.members || []).some(
				(member) => member.member_user === values.member_user
			);
			if (already_added) {
				frappe.msgprint(
					__("User {0} is already a Plan Team member.", [values.member_user])
				);
				return;
			}
			frm.add_child("members", {
				member_user: values.member_user,
				role: values.role,
			});
			frm.refresh_field("members");
			frm.dirty();
			dialog.hide();
		},
	});
	dialog.show();
}

function customize_row_editor(frm, cdt, cdn) {
	let grid = frm.fields_dict["members"] && frm.fields_dict["members"].grid;
	if (!grid || !grid.wrapper) return;

	const apply_customization = () => {
		let $row_editor = grid.wrapper.find(".grid-row-open");
		if ($row_editor.length > 0) {
			// Hide unnecessary buttons in the top toolbar
			$row_editor
				.find(
					".grid-insert-row-below, .grid-insert-row, .grid-duplicate-row, .grid-move-row, .grid-collapse-row"
				)
				.hide();

			// Customize bottom-right button
			let $bottom_btn = $row_editor.find(".grid-append-row");
			if ($bottom_btn.length > 0) {
				$bottom_btn
					.text(__("Save"))
					.removeClass("btn-secondary btn-default")
					.addClass("btn-primary")
					.off("click")
					.on("click", function (e) {
						e.preventDefault();
						e.stopImmediatePropagation();
						let $collapse_btn = $row_editor.find(".grid-collapse-row");
						if ($collapse_btn.length > 0) {
							$collapse_btn.click();
						}
					});
			}
		}
	};

	apply_customization();
	setTimeout(apply_customization, 50);
	setTimeout(apply_customization, 200);
}

function schedule_description_height(frm) {
	match_plan_description_height(frm);
	requestAnimationFrame(() => match_plan_description_height(frm));
	[50, 150, 300, 600, 1000].forEach((delay) => {
		setTimeout(() => match_plan_description_height(frm), delay);
	});
}

function apply_plan_locks(frm) {
	const is_draft = !frm.doc.status || frm.doc.status === "Draft";
	const is_closed = frm.doc.status === "Archived";
	const can_manage_status =
		frm.perm &&
		frm.perm[0] &&
		frm.perm[0].write &&
		(frappe.user.has_role("System Manager") ||
			frappe.user.has_role("OKR Admin") ||
			frappe.session.user === "Administrator");

	["company", "owner_user"].forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", !is_draft);
	});
	["financial_year", "sprint_frequency"].forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", is_closed);
	});
	frm.set_df_property("planned_activation_date", "hidden", 0);
	frm.toggle_display("planned_activation_date", true);
	frm.set_df_property("planned_activation_date", "read_only", is_closed);
	frm.set_df_property("planned_activation_date", "reqd", is_draft);
	frm.set_df_property("description", "read_only", is_closed);
	frm.set_df_property("progress", "hidden", 1);

	if (!frm.doc.status) {
		frm.set_value("status", "Draft");
	}
	frm.set_df_property("status", "hidden", 0);
	frm.set_df_property("status", "read_only", !can_manage_status);
}

function fix_okr_plan_layout(frm) {
	// 1. Force the parent page-container to be full width and NOT display grid
	let container = frm.wrapper.closest(".page-container");
	if (container.length) {
		container[0].style.setProperty("display", "block", "important");
		container[0].style.setProperty("max-width", "98%", "important");
		container[0].style.setProperty("width", "98%", "important");
	}

	// 2. Force layout-main and layout-main-section elements to take 100% width
	let layout_main = frm.wrapper.closest(".layout-main");
	if (layout_main.length) {
		layout_main[0].style.setProperty("max-width", "100%", "important");
		layout_main[0].style.setProperty("width", "100%", "important");
	}
	let layout_section = frm.wrapper.closest(".layout-main-section");
	if (layout_section.length) {
		layout_section[0].style.setProperty("max-width", "100%", "important");
		layout_section[0].style.setProperty("width", "100%", "important");
	}

	// 3. Force the form-page inside the layout section to be grid layout if viewport >= 992px
	let form_page = frm.wrapper.find(".form-page");
	if (form_page.length) {
		if (window.innerWidth >= 992) {
			form_page[0].style.setProperty("display", "grid", "important");
			form_page[0].style.setProperty("grid-template-columns", "1.1fr 1fr", "important");
			form_page[0].style.setProperty("gap", "16px 20px", "important");
			form_page[0].style.setProperty("align-items", "flex-start", "important");
			form_page[0].style.setProperty("width", "100%", "important");

			// 4. Force specific sections (like plan_team_section and technical_section) to span full width
			let plan_team_section = frm.wrapper.find(
				'.form-section[data-fieldname="plan_team_section"]'
			);
			if (plan_team_section.length) {
				plan_team_section[0].style.setProperty("grid-column", "1 / -1", "important");
			}
			let technical_section = frm.wrapper.find(
				'.form-section[data-fieldname="technical_section"]'
			);
			if (technical_section.length) {
				technical_section[0].style.setProperty("grid-column", "1 / -1", "important");
			}
		} else {
			form_page[0].style.removeProperty("display");
			form_page[0].style.removeProperty("grid-template-columns");
			form_page[0].style.removeProperty("gap");
			form_page[0].style.removeProperty("align-items");
			form_page[0].style.removeProperty("width");
		}
	}
}


function update_objective_connection_badge(frm) {
	if (!frm || frm.is_new() || !frm.doc?.name) return;

	const render_count = (count) => {
		const $links = frm.$wrapper.find('.form-dashboard .document-link[data-doctype="OKR Objective"]');
		if (!$links.length) return;

		$links.each(function () {
			const $link = $(this);
			let $count = $link.find(".count");
			if (!$count.length) {
				$count = $('<span class="count"></span>').prependTo($link.find(".document-link-badge"));
			}
			const count_num = cint(count);
			const count_text = count_num > 99 ? "99+" : `${count_num}`;
			$count
				.text(count_text)
				.removeClass("hidden")
				.css({ display: "inline-block" })
				.attr("title", __("{0} linked OKR Objective(s)", [count_num]));
			$link.removeClass("hidden text-muted");
		});
	};

	if (frm.doc.objective_count !== undefined && frm.doc.objective_count !== null) {
		render_count(frm.doc.objective_count);
	}

	frappe.db.count("OKR Objective", {
		filters: { parent_plan: frm.doc.name }
	}).then((count) => {
		render_count(count);
		if (frm.doc.objective_count !== count) {
			frm.doc.objective_count = count;
		}
	});

	if (frm.dashboard) {
		frm.dashboard._fetched_counts = false;
		if (typeof frm.dashboard.set_open_count === "function") {
			frm.dashboard.set_open_count();
		}
	}
}
