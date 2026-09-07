const okr_management = window.okr_management;
frappe.pages["okr-workspace"].on_page_load = function (wrapper) {
	wrapper.okr_workspace = new OKRWorkspace(wrapper);
};

frappe.pages["okr-workspace"].on_page_show = function (wrapper) {
	const workspace = wrapper.okr_workspace;
	if (workspace?.options) {
		workspace.load_options();
	}
};

class OKRWorkspace {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({ parent: wrapper, single_column: true });
		this.$body = $('<div class="okr-workspace-page"></div>').appendTo(this.page.main);
		this.filters = Object.assign(
			{ plan: "", owner: "me" },
			frappe.session.okr_workspace_filters || {}
		);
		delete this.filters.year;
		delete this.filters.level;
		if (this.filters.owner === "all") this.filters.owner = "team";
		this.state = {
			objectives: {},
			key_results: {},
			action_history: {},
			action_history_all: {},
			action_checkin: null,
			measurement_action: null,
			selected_objective: null,
		};
		this.attachment = "";
		this.saving_checkin = false;
		this.render_shell();
		this.bind_events();
		this.load_options();
	}

	render_shell() {
		this.$body.html(`
                        <div class="okr-ws-shell">
                                <aside class="okr-ws-rail">
                                        <div class="okr-ws-brand">${__("OKR Workspace")}</div>
                                        <div class="okr-ws-rail-title">${__("Objectives")}</div>
                                        <div data-objective-rail></div>
                                </aside>
                                <main class="okr-ws-main">
                                        <div class="okr-ws-topbar">
                                                <div class="okr-ws-active-filters" data-active-filters></div>
                                                <button class="okr-icon-toggle-all" data-toggle-all-krs title="${__(
													"Collapse/Expand All"
												)}">${frappe.utils.icon("collapse", "sm")}</button>
                                                <button class="okr-icon-filter" data-open-filter title="${__(
													"Filter"
												)}">${frappe.utils.icon("filter", "sm")}</button>
                                        </div>
                                        <div class="okr-filter-popover" data-filter-popover style="display:none;">
                                                <div class="okr-pop-head"><strong>${__(
													"Filter Context"
												)}</strong><button data-close-filter>${frappe.utils.icon(
			"close",
			"sm"
		)}</button></div>
                                                <div class=okr-pop-content>
                                                <div class="okr-filter-group"><label>${__(
													"Plan"
												)}</label><div data-plan-pills class="okr-pill-row okr-pill-row-wrap"></div></div>
                                                <div class="okr-filter-group"><label>${__(
													"Owner"
												)}</label><div data-owner-pills class="okr-pill-row"></div></div>
                                                </div>
                                                <div class="okr-pop-actions"><button class="btn btn-sm btn-default" data-close-filter>${__(
													"Cancel"
												)}</button><button class="btn btn-sm btn-primary" data-apply-filter>${__(
			"Apply Filter"
		)}</button></div>
                                                </div>
                                        <div data-workspace-content></div>
                                </main>
                        </div>
                `);
	}

	bind_events() {
		$(window)
			.off("focus.okr-workspace")
			.on("focus.okr-workspace", () => {
				if ((frappe.get_route() || [])[0] === "okr-workspace" && this.options) {
					this.load_options();
				}
			});
		this.$body.on("click", "[data-open-filter]", () =>
			this.$body.find("[data-filter-popover]").toggle()
		);
		this.$body.on("click", "[data-close-filter]", () =>
			this.$body.find("[data-filter-popover]").hide()
		);
		this.$body.on("click", "[data-pill]", (e) => {
			const $pill = $(e.currentTarget);
			this.filters[$pill.data("field")] = $pill.data("value") || "";
			this.render_filter_pills();
		});
		this.$body.on("click", "[data-apply-filter]", () => {
			frappe.session.okr_workspace_filters = Object.assign({}, this.filters);
			this.$body.find("[data-filter-popover]").hide();
			this.load();
		});
		this.$body.on("click", "[data-toggle-objective]", (e) => {
			if ($(e.target).closest("a, button, input, select, textarea").length) return;
			e.preventDefault();
			e.stopPropagation();
			const objName = $(e.currentTarget).data("toggle-objective");
			const $card = $(e.currentTarget).closest(".okr-objective-card");
			const $collapse = $card.find("> .okr-collapse");
			const $chevron = $card.find(".okr-obj-chevron");

			this.state.objectives[objName] = !this.state.objectives[objName];

			$collapse.stop(true, true).slideToggle(180);
			if (this.state.objectives[objName]) {
				$chevron.removeClass("collapsed").addClass("expanded");
			} else {
				$chevron.removeClass("expanded").addClass("collapsed");
			}
		});
		this.$body.on("click", "[data-toggle-all-krs]", () => {
			this.toggle_all_krs();
		});
		this.$body.on("click", "[data-open-kr]", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const krName = $(e.currentTarget).data("open-kr");
			if (krName) {
				frappe.set_route("Form", "OKR Key Result", krName);
			}
		});
		this.$body.on("click", "[data-open-kr-actions]", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const krName = $(e.currentTarget).data("open-kr-actions");
			if (!krName) return;
			this.state.key_results[krName] = true;
			this.render_content();
			requestAnimationFrame(() => {
				const $card = this.$body
					.find("[data-kr-card]")
					.filter((_, element) => $(element).data("kr-card") === krName)
					.first();
				const target = $card.find(".okr-action-progress").first()[0] || $card[0];
				target?.scrollIntoView({ behavior: "smooth", block: "center" });
			});
		});
		this.$body.on("click", "[data-toggle-kr]", (e) => {
			if ($(e.target).closest("a, button, input, select, textarea").length) return;
			e.preventDefault();
			e.stopPropagation();
			const krName = $(e.currentTarget).data("toggle-kr");
			const $card = $(e.currentTarget).closest(".okr-kr-card");
			const $collapse = $card.find("> .okr-collapse");
			const $chevron = $card.find(".okr-kr-chevron");

			this.state.key_results[krName] = !this.state.key_results[krName];

			$collapse.stop(true, true).slideToggle(180);
			if (this.state.key_results[krName]) {
				$chevron.removeClass("collapsed").addClass("expanded");
			} else {
				$chevron.removeClass("expanded").addClass("collapsed");
			}
			this.update_toggle_all_button();
		});
		this.$body.on("click", "[data-toggle-history]", (e) => {
			if (
				$(e.target)
					.closest("a, button, input, select, textarea, [data-open-measurement]")
					.not(".okr-history-toggle").length
			)
				return;
			e.preventDefault();
			e.stopPropagation();
			const actionName = $(e.currentTarget).data("toggle-history");
			if (this.state.action_checkin === actionName) {
				this.state.action_checkin = null;
				this.state.action_history[actionName] = false;
				this.render_content();
				return;
			}
			const $block = $(e.currentTarget).closest(".okr-action-block");
			const $collapse = $block.find("> .okr-history-collapse");
			const $chevron = $block.find(".okr-ai-chevron, .okr-history-chevron");

			this.state.action_history[actionName] = !this.state.action_history[actionName];
			$collapse.stop(true, true).slideToggle(180);
			$chevron.toggleClass("expanded", this.state.action_history[actionName]);
			$chevron.toggleClass("collapsed", !this.state.action_history[actionName]);
			$(e.currentTarget)
				.find(".okr-history-toggle")
				.attr("aria-expanded", this.state.action_history[actionName] ? "true" : "false");
		});
		this.$body.on("click", "[data-toggle-all-history]", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const actionName = $(e.currentTarget).data("toggle-all-history");
			this.state.action_history_all[actionName] = !this.state.action_history_all[actionName];
			this.render_content();
		});
		this.$body.on("click", "[data-open-checkin]", (e) => {
			e.stopPropagation();
			this.open_checkin($(e.currentTarget).data("open-checkin"));
		});
		this.$body.on("click", "[data-cancel-checkin]", () => {
			this.state.action_checkin = null;
			this.render_content();
		});
		this.$body.on("click", "[data-save-checkin]", () => this.save_checkin());
		this.$body.on("click", "[data-open-measurement]", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const actionName = $(e.currentTarget).data("open-measurement");
			this.state.measurement_action =
				this.state.measurement_action === actionName ? null : actionName;
			this.state.action_checkin = null;
			this.render_content();
		});
		this.$body.on("click", "[data-cancel-measurement]", () => {
			this.state.measurement_action = null;
			this.render_content();
		});
		this.$body.on("click", "[data-save-measurement]", () => this.save_measurement());
		this.$body.on("input", "[data-ws-progress]", (e) => {
			const $input = $(e.currentTarget);
			const actual = flt($input.val(), 2);
			const baseline = flt($input.data("baseline"), 2);
			const target = flt($input.data("target"), 2);
			const metricType = $input.data("metric-type");
			const direction = $input.data("direction");
			let completion = 0;
			if (metricType === "Boolean") completion = actual ? 100 : 0;
			else if (target !== baseline)
				completion =
					direction === "Decrease"
						? ((baseline - actual) / (baseline - target)) * 100
						: ((actual - baseline) / (target - baseline)) * 100;
			completion = Math.min(100, Math.max(0, completion));
			$input
				.closest(".okr-inline-checkin")
				.find("[data-ws-completion]")
				.text(`${flt(completion, 2)}%`);
		});
		this.$body.on("click", "[data-attach-file]", () => this.attach_file());
		this.$body.on("click", "[data-remove-attachment]", () => {
			this.attachment = "";
			this.render_attachment();
		});
		this.$body.on("click", "[data-preview-attachment]", (e) => {
			e.preventDefault();
			okr_management.preview_attachment($(e.currentTarget).attr("data-preview-attachment"));
		});
		this.$body.on("click", "[data-adjust-filter]", () =>
			this.$body.find("[data-filter-popover]").show()
		);
		this.$body.on("click", "[data-select-objective]", (e) => {
			e.preventDefault();
			this.state.selected_objective = $(e.currentTarget).data("select-objective");
			this.state.objectives[this.state.selected_objective] = true;
			this.state.action_checkin = null;
			this.render_content();
		});
		this.$body.on("click", ".okr-open-link", (e) => {
			e.stopPropagation();
		});
	}

	load_options() {
		frappe.call({
			method: "okr_management.okr_management.page.okr_workspace.okr_workspace.get_filter_options",
			callback: (r) => {
				this.options = r.message || {};
				const availablePlans = new Set(
					(this.options.plans || []).map((plan) => plan.name)
				);
				if (!this.filters.plan || !availablePlans.has(this.filters.plan)) {
					this.filters.plan = this.options.default_plan || "";
				}
				this.render_filter_pills();
				this.load();
			},
		});
	}

	load() {
		if (frappe.route_options && frappe.route_options.objective) {
			const target_obj = frappe.route_options.objective;
			delete frappe.route_options.objective;

			frappe.db.get_value("OKR Objective", target_obj, "parent_plan").then((r) => {
				const val = r.message || {};
				this.filters.plan = val.parent_plan || this.options.default_plan || "";
				this.filters.owner = "team";
				this.state.selected_objective = target_obj;
				this.render_filter_pills();
				this.load();
			});
			return;
		}

		frappe.call({
			method: "okr_management.okr_management.page.okr_workspace.okr_workspace.get_workspace_data",
			args: this.filters,
			freeze: true,
			freeze_message: __("Loading OKR Workspace..."),
			callback: (r) => {
				this.data = r.message || { objectives: [] };
				const objectiveNames = (this.data.objectives || []).map((obj) => obj.name);
				if (!objectiveNames.includes(this.state.selected_objective)) {
					this.state.selected_objective = objectiveNames[0] || null;
				}
				this.state.objectives = {};
				this.state.key_results = {};
				(this.data.objectives || []).forEach((obj) => {
					this.state.objectives[obj.name] = true;
					(obj.key_results || []).forEach((kr) => {
						this.state.key_results[kr.name] = true;
					});
				});
				this.render_active_filters();
				this.render_content();
			},
		});
	}

	render_filter_pills() {
		if (!this.options) return;
		this.render_pill_group(
			"plan",
			(this.options.plans || []).map((plan) => ({
				label:
					(plan.plan_name || plan.name) +
					(plan.status === "Archived" ? ` (${__("Archived")})` : ""),
				value: plan.name,
			}))
		);
		this.render_pill_group("owner", [
			{ label: __("My OKRs"), value: "me" },
			{ label: __("My Team OKRs"), value: "team" },
		]);
	}

	render_pill_group(field, items) {
		const selected = this.filters[field] || "";
		this.$body.find(`[data-${field}-pills]`).html(
			items
				.map(
					(item) => `
                        <button class="okr-filter-pill ${
							selected === item.value ? "active" : ""
						}" data-pill data-field="${field}" data-value="${frappe.utils.escape_html(
						item.value
					)}">${frappe.utils.escape_html(item.label)}</button>
                `
				)
				.join("")
		);
	}

	render_active_filters() {
		const ownerLabels = { me: __("My OKRs"), team: __("My Team OKRs") };
		const labels = [this.plan_label(), ownerLabels[this.filters.owner] || ownerLabels.me];
		this.$body.find("[data-active-filters]").html(
			labels
				.filter(Boolean)
				.map((v) => `<span>${frappe.utils.escape_html(v)}</span>`)
				.join("")
		);
	}

	plan_label() {
		const plan = (this.options.plans || []).find((row) => row.name === this.filters.plan);
		return plan ? plan.plan_name || plan.name : __("Plan");
	}

	render_content() {
		const objectives = this.data.objectives || [];
		this.render_rail(objectives);
		if (!objectives.length) {
			this.$body.find("[data-workspace-content]").html(this.empty_state());
			return;
		}
		const selected =
			objectives.find((obj) => obj.name === this.state.selected_objective) || objectives[0];
		this.state.selected_objective = selected.name;
		this.state.objectives[selected.name] = true;
		(selected.key_results || []).forEach((kr) => {
			this.state.key_results[kr.name] = true;
		});
		this.$body.find("[data-workspace-content]").html(this.objective_card(selected));
		this.render_attachment();
		this.update_toggle_all_button();
	}


	toggle_all_krs() {
		const objectives = this.data.objectives || [];
		const selected =
			objectives.find((obj) => obj.name === this.state.selected_objective) || objectives[0];
		if (!selected) return;
		const krs = selected.key_results || [];
		if (!krs.length) return;

		const anyOpen = krs.some((kr) => this.state.key_results[kr.name] !== false);
		const targetState = !anyOpen;

		krs.forEach((kr) => {
			this.state.key_results[kr.name] = targetState;
		});

		const $cards = this.$body.find(".okr-kr-card");
		const $collapses = $cards.find("> .okr-collapse");
		const $chevrons = $cards.find(".okr-kr-chevron");

		if (targetState) {
			$collapses.stop(true, true).slideDown(180).addClass("open");
			$chevrons.removeClass("collapsed").addClass("expanded");
		} else {
			$collapses.stop(true, true).slideUp(180).removeClass("open");
			$chevrons.removeClass("expanded").addClass("collapsed");
		}

		this.update_toggle_all_button();
	}

	update_toggle_all_button() {
		const $btn = this.$body.find("[data-toggle-all-krs]");
		if (!$btn.length) return;
		const objectives = this.data.objectives || [];
		const selected =
			objectives.find((obj) => obj.name === this.state.selected_objective) || objectives[0];
		const krs = selected?.key_results || [];
		if (!krs.length) {
			$btn.hide();
			return;
		}
		$btn.show();
		const anyOpen = krs.some((kr) => this.state.key_results[kr.name] !== false);
		const iconName = anyOpen ? "collapse" : "expand";
		const titleText = anyOpen ? __("Collapse All") : __("Expand All");
		$btn.attr("title", titleText).attr("aria-label", titleText).html(frappe.utils.icon(iconName, "sm"));
	}

	render_rail(objectives) {
		const html = objectives.length
			? objectives
					.map(
						(obj) => `
                        <a class="okr-rail-objective ${
							this.state.selected_objective === obj.name ? "active" : ""
						}" href="#${obj.name}" data-select-objective="${
							obj.name
						}"><span class="okr-rail-dot"></span><strong>${frappe.utils.escape_html(
							obj.objective_title || obj.name
						)}</strong><small>${frappe.utils.escape_html(
							obj.creator_full_name || obj.owner || "-"
						)}</small><small>${cint(obj.progress || 0)}% · ${frappe.utils.escape_html(
							obj.status || ""
						)}</small></a>
                `
					)
					.join("")
			: `<div class="okr-rail-empty">${__("No objectives for selected filter")}</div>`;
		this.$body.find("[data-objective-rail]").html(html);
	}

	objective_card(obj) {
		const open = this.state.objectives[obj.name];
		const progress = cint(obj.progress || 0);
		const completionClass = progress >= 70 ? "good" : "warn";
		const completionColor = progress >= 70 ? "#16a34a" : "#eab308";

		// Summary cards calculation
		const key_results = obj.key_results || [];
		const total_krs = key_results.length;
		const today = this.data.today || frappe.datetime.now_date();

		let blocked_count = 0;
		let at_risk_count = 0;
		let on_track_count = 0;

		key_results.forEach((kr) => {
			if (this.is_kr_blocked(kr)) {
				blocked_count++;
			} else if (this.is_kr_at_risk(kr, today)) {
				at_risk_count++;
			} else {
				const kr_progress = flt(kr.target_progress || 0);
				if (kr_progress >= 70) {
					on_track_count++;
				}
			}
		});

		return `
                        <section class="okr-objective-card" id="${obj.name}">
                                <div class="okr-objective-head">
                                        <div class="okr-objective-head-left"><span class="okr-type-dot">OBJ</span><div style="display:flex;flex-direction:column;"><div class="okr-title-with-period"><h2>${frappe.utils.escape_html(
			obj.objective_title || obj.name
		)}</h2>${this.period_badge(obj.period_label)}</div><small style="font-size:11px;color:#64748b;font-weight:500;margin-top:2px;">${frappe.utils.escape_html(
			obj.creator_full_name || obj.owner || "-"
		)}</small></div></div><span class="okr-status okr-${frappe.scrub(
			obj.status || ""
		)}">${frappe.utils.escape_html(obj.status || "")}</span>
                                </div>
                                <div class="okr-collapse open" style="display: block;">
                                        <div class="okr-overview-summary">
                                                <div class="okr-summary-card okr-completion-card">
                                                        <span class="okr-summary-card-label">${__(
															"Completion"
														)}</span>
                                                        <div class="okr-donut-chart">
                                                                <svg class="okr-donut-svg" viewBox="0 0 36 36">
                                                                        <path class="okr-donut-ring" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e2e8f0" stroke-width="3"></path>
                                                                        <path class="okr-donut-segment" stroke="${completionColor}" stroke-width="3" stroke-dasharray="${progress}, 100" stroke-linecap="round" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none"></path>
                                                                </svg>
                                                                <div class="okr-donut-number ${completionClass}">${progress}%</div>
                                                        </div>
                                                </div>
                                                ${this.need_attention_panel(
													key_results,
													today,
													progress
												)}
                                        </div>
                                        ${(obj.key_results || [])
											.map((kr) => this.kr_card(kr))
											.join("")}
                                </div>
                        </section>
                `;
	}

	need_attention_panel(key_results, today, completion) {
		const priorityRank = { High: 0, Medium: 1, Low: 2 };
		const items = key_results
			.map((kr) => {
				const blocked = this.is_kr_blocked(kr);
				const atRisk = !blocked && this.is_kr_at_risk(kr, today);
				return {
					kr,
					reasons: this.kr_attention_reasons(kr, today),
					rank: blocked ? 0 : atRisk ? 1 : 2,
					label: blocked
						? __("Blocked")
						: atRisk
						? __("Need Attention")
						: __("On Track"),
					tone: blocked ? "blocked" : atRisk ? "risk" : "on-track",
				};
			})
			.sort(
				(a, b) =>
					a.rank - b.rank ||
					(priorityRank[a.kr.priority] ?? 3) - (priorityRank[b.kr.priority] ?? 3)
			);
		const attentionCount = items.filter((item) => item.rank < 2).length;
		if (!attentionCount) {
			return `
				<div class="okr-attention-panel okr-all-clear-panel">
					<div class="okr-all-clear-head"><span aria-hidden="true">&#10022;</span>${__(
						"All Clear &middot; You\x27re on track"
					)}</div>
					<div class="okr-all-clear-body">
						<span class="okr-all-clear-check" aria-hidden="true">&#10003;</span>
						<div><strong>${__("Nothing needs your attention")}</strong><small>${__(
				"No active items"
			)} &middot; ${completion}% ${__("complete")}</small></div>
					</div>
				</div>`;
		}
		const rows = items.length
			? items
					.map(
						(item) => `
							<div class="okr-attention-item ${item.tone}">
								<span class="okr-attention-dot"></span>
								<div>
									<strong>${frappe.utils.escape_html(item.kr.key_result_title || item.kr.name)}</strong>
									<ul class="okr-attention-reasons">${item.reasons
										.map(
											(reason) =>
												"<li>" + frappe.utils.escape_html(reason) + "</li>"
										)
										.join("")}</ul>
								</div>
								<span class="okr-attention-actions">
					<span class="okr-attention-status">${item.label}</span>
				</span>
							</div>`
					)
					.join("")
			: `<div class="okr-attention-empty">${__("No Key Results")}</div>`;
		return `
			<div class="okr-attention-panel">
				<div class="okr-attention-head"><span>${__(
					"Need Attention"
				)}</span><strong>${attentionCount}</strong></div>
				<div class="okr-attention-list">${rows}</div>
			</div>`;
	}

	kr_attention_reasons(kr, todayStr) {
		const reasons = [];
		const today = moment(todayStr);
		const formatDate = (value) => frappe.datetime.str_to_user(value);
		const actionTitle = (action) => action.action_item_title || action.name;
		if (kr.status === "Blocked") reasons.push(__("Key Result is marked Blocked."));
		if (kr.status === "At Risk") reasons.push(__("Key Result is marked At Risk."));
		const krProgress = flt(kr.target_progress || 0);
		if (kr.end_date) {
			const days = moment(kr.end_date).diff(today, "days");
			if (days >= 0 && days <= 14 && krProgress < 70)
				reasons.push(
					__(
						"Key Result ends on {0}: {1} day(s) left and progress is {2}% (below 70%).",
						[formatDate(kr.end_date), days, krProgress]
					)
				);
		}
		for (const action of kr.action_items || []) {
			const title = actionTitle(action);
			const progress = flt(action.progress || 0);
			if (action.status === "Blocked")
				reasons.push(__("Action Item ‘{0}’ is marked Blocked.", [title]));
			if (action.status === "At Risk")
				reasons.push(__("Action Item ‘{0}’ is marked At Risk.", [title]));
			if (!action.due_date) continue;
			const due = moment(action.due_date);
			const complete =
				action.status === "Completed" || action.status === "Archived" || progress >= 100;
			if (due.isBefore(today, "day") && !complete) {
				const overdueDays = today.diff(due, "days");
				reasons.push(
					__("Action Item ‘{0}’ was due on {1}: {2} day(s) overdue, progress {3}%.", [
						title,
						formatDate(action.due_date),
						overdueDays,
						progress,
					])
				);
			}
			const days = due.diff(today, "days");
			if (days >= 0 && days <= 14 && progress < 70)
				reasons.push(
					__(
						"Action Item ‘{0}’ is due on {1}: {2} day(s) left and progress is {3}% (below 70%).",
						[title, formatDate(action.due_date), days, progress]
					)
				);
		}
		return reasons.length ? reasons : [__("Key Result is on track.")];
	}

	period_badge(label) {
		return label
			? `<span class="okr-period-badge">${frappe.utils.escape_html(label)}</span>`
			: "";
	}

	kr_card(kr) {
		const open = this.state.key_results[kr.name];
		const progress = flt(kr.target_progress || 0, 2);
		const statusClass = progress >= 80 ? "good" : progress >= 45 ? "warn" : "risk";
		const progressDisplay = this.kr_progress_display(kr);
		const assigneeName = kr.assignee_full_name || kr.assignee || "";
		return `
                        <div class="okr-kr-card" data-kr-card="${frappe.utils.escape_html(kr.name)}">
                                <div class="okr-kr-head" data-toggle-kr="${kr.name}">
                                        <div>
                                                <span class="okr-kr-chevron ${
													open ? "expanded" : "collapsed"
												}"></span>
                                                <span class="okr-kr-icon">KR</span>
                                                <div style="display: flex; flex-direction: column;">
                                                        <div class="okr-title-with-period"><strong title="${frappe.utils.escape_html(
															kr.key_result_title || kr.name
														)}">${frappe.utils.escape_html(
			kr.key_result_title || kr.name
		)}</strong>${this.period_badge(kr.period_label)}</div>
                                                        ${
															assigneeName
																? `<span style="font-size: 11px; color: #64748b; font-weight: 500; margin-top: 2px;">${frappe.utils.escape_html(
																		assigneeName
																  )}</span>`
																: ""
														}
                                                </div>
                                        </div>
                                        <div class="okr-kr-meta">
                                                <button type="button" class="okr-signal ${statusClass}" data-open-kr-actions="${frappe.utils.escape_html(
			kr.name
		)}" title="${__("View Action Item measurements")}">${frappe.utils.escape_html(
			progressDisplay
		)}</button>
                                                <button type="button" class="okr-kr-redirect-btn" data-open-kr="${frappe.utils.escape_html(
			kr.name
		)}" title="${__("Open Key Result")}" aria-label="${__("Open Key Result")}">${frappe.utils.icon("arrow-up-right", "xs")}</button>
                                        </div>
                                </div>
                                <div class="okr-collapse ${open ? "open" : ""}" style="${
			open ? "display: block;" : "display: none;"
		}">${
			(kr.action_items || []).length
				? kr.action_items.map((ai) => this.action_row(ai, kr)).join("")
				: this.no_actions()
		}</div>
                        </div>
                `;
	}

	action_row(ai, kr) {
		const meas = this.get_effective_action_measurement(ai, kr);
		const progress = flt(meas.progress, 2);
		const historyOpen = this.state.action_history[ai.name];
		const checkinOpen = this.state.action_checkin === ai.name;
		const measurementOpen = this.state.measurement_action === ai.name;
		const historyCount = (ai.history || []).length;
		const actionProgressTone =
			(ai.status || "").toLowerCase() === "blocked"
				? "blocked"
				: progress >= 70
				? "good"
				: "warn";
		const ownerName = ai.owner_full_name || ai.owner_user || "";
		const progressDisplay = this.action_progress_display(ai, kr, meas);
		const latestCheckin = (ai.history || [])[0];
		const latestCheckinDate =
			latestCheckin && latestCheckin.checkin_date
				? frappe.datetime.str_to_user(latestCheckin.checkin_date)
				: "-";
		return `
                        <div class="okr-action-block">
                                <div class="okr-action-row" data-toggle-history="${ai.name}">
                                        <div class="okr-action-title">
                                                <span class="okr-ai-chevron ${
													historyOpen ? "expanded" : "collapsed"
												}"></span>
                                                <span class="okr-ai-icon">AI</span>
                                                <div style="display: flex; flex-direction: column;">
                                                        <div class="okr-title-with-period"><strong title="${frappe.utils.escape_html(
															ai.action_item_title || ai.name
														)}">${frappe.utils.escape_html(
			ai.action_item_title || ai.name
		)}</strong></div>
                                                        ${
															ownerName
																? `<span style="font-size: 11px; color: #64748b; font-weight: 500; margin-top: 2px;">${frappe.utils.escape_html(
																		ownerName
																  )}</span>`
																: ""
														}
                                                </div>
                                        </div>
                                        <span class="okr-status ${frappe.scrub(
											ai.status || ""
										)}">${frappe.utils.escape_html(ai.status || "")}</span>
                                        <div class="okr-action-progress ${actionProgressTone} ${ai.can_edit_measurement ? "is-editable" : "is-locked"}" ${
			ai.can_edit_measurement
				? `data-open-measurement="${ai.name}" role="button" tabindex="0" title="${__("Edit Action Item measurement")}"`
				: `title="${ai.measurement_locked ? __("Measurement configuration is locked by the Key Result owner.") : __("You are not authorized to edit this measurement.")}"`
		}><div class="okr-bar"><i style="width:${Math.min(
			100,
			progress
		)}%"></i></div><strong>${progressDisplay}</strong></div>
                                        <div class="okr-action-meta-col">
                                                <button type="button" class="okr-history-toggle" aria-expanded="${
													historyOpen ? "true" : "false"
												}">
                                                        ${historyCount} ${__("Check-ins")}
                                                        <span class="okr-history-chevron ${
															historyOpen ? "expanded" : "collapsed"
														}"></span>
                                                </button>
                                                <div class="okr-action-last-checkin">${latestCheckinDate}</div>
                                        </div>
                                </div>
                                ${checkinOpen ? this.checkin_panel(ai, kr) : ""}
                                ${measurementOpen ? this.measurement_panel(ai, kr) : ""}
                                <div class="okr-history-collapse ${
									historyOpen ? "open" : ""
								}" style="${
			historyOpen ? "display: block;" : "display: none;"
		}">${this.history_timeline(ai, kr, meas)}</div>
                        </div>
                `;
	}


	measurement_panel(ai, kr) {
		const meas = this.get_effective_action_measurement(ai, kr);
		const type = meas.metric_type || "Percentage";
		const direction = meas.metric_direction || "Increase";
		return `
			<div class="okr-inline-checkin okr-inline-measurement" data-measurement-action="${ai.name}">
				<div class="okr-inline-context">
					<strong>${__("Measurement Configuration")}</strong>
					<button type="button" class="okr-close-btn" data-cancel-measurement title="${__("Close")}">
						<span class="okr-close-icon">✕</span> ${__("Close")}
					</button>
				</div>
				<div class="okr-inline-fields">
					<div class="okr-measurement-grid">
						<label><span>${__("Measurement Type")}</span><select class="form-control" data-measurement-type>
							${["Percentage", "Number", "Currency", "Boolean"].map((value) =>
								`<option value="${value}" ${type === value ? "selected" : ""}>${__(value)}</option>`
							).join("")}
						</select></label>
						<label><span>${__("Goal Direction")}</span><select class="form-control" data-measurement-direction>
							<option value="Increase" ${direction === "Increase" ? "selected" : ""}>${__("Increase")}</option>
							<option value="Decrease" ${direction === "Decrease" ? "selected" : ""}>${__("Decrease")}</option>
						</select></label>
						<label><span>${__("Starting Value")}</span><input class="form-control" type="number" step="0.01" data-measurement-baseline value="${meas.baseline_value}"></label>
						<label><span>${__("Target Value")}</span><input class="form-control" type="number" step="0.01" data-measurement-target value="${meas.target_value}"></label>
						<label><span>${__("Current Value")}</span><input class="form-control" type="number" step="0.01" data-measurement-current value="${meas.current_value}"></label>
					</div>
					<div class="okr-inline-actions">
						<button type="button" class="btn btn-sm btn-default" data-cancel-measurement>${__("Cancel")}</button>
						<button type="button" class="btn btn-sm btn-dark" data-save-measurement>${__("Save Measurement")}</button>
					</div>
				</div>
			</div>
		`;
	}

	checkin_panel(ai, kr) {
		const currentStatus = ai.status || "In Progress";
		const isCustom = Boolean(ai.customize_measurement);
		const metricType = isCustom && ai.metric_type ? ai.metric_type : (kr.metric_type || "Percentage");
		const baseline = flt(isCustom ? ai.baseline_value : (kr.baseline_value || 0), 2);
		const target = flt(isCustom ? ai.target_value : (kr.target_value || 0), 2);
		const minimum = Math.min(baseline, target);
		const maximum = Math.max(baseline, target);
		const actual = flt(isCustom ? (ai.current_value !== undefined && ai.current_value !== null ? ai.current_value : baseline) : (kr.current_value || baseline), 2);
		const direction = isCustom && ai.metric_direction ? ai.metric_direction : (kr.metric_direction || "Increase");
		const valueLabel =
			metricType === "Currency"
				? __("Current Amount ({0})", [isCustom ? "" : (kr.currency || "")])
				: metricType === "Number"
				? __("Current Value")
				: __("Current Percentage (%)");
		const completionDisplay = flt(isCustom ? (ai.progress || 0) : (kr.target_progress || 0), 2);
		return `
			<div class="okr-inline-checkin">
				<div class="okr-inline-context">
					<div></div>
					<div class="okr-context-collapse-wrap">
						<button type="button" class="okr-close-btn" data-cancel-checkin title="${__("Close")}">
							<span class="okr-close-icon">✕</span> ${__("Close")}
						</button>
					</div>
				</div>
				<div class="okr-inline-fields okr-quick-checkin-form">
					<div class="okr-checkin-row">
						<div class="okr-checkin-field">
							<label>${valueLabel}</label>
							<input class="form-control" type="number" min="${minimum}" max="${maximum}" step="0.01" data-ws-progress data-baseline="${baseline}" data-target="${target}" data-metric-type="${metricType}" data-direction="${direction}" value="${actual}">
							<small class="text-muted">${__("Allowed range: {0} to {1}", [minimum, maximum])}</small>
						</div>
						<div class="okr-checkin-field">
							<label>${__("Completion")}</label>
							<div class="form-control" data-ws-completion>${completionDisplay}%</div>
						</div>
						<div class="okr-checkin-field">
							<label>${__("Status")}</label>
							<select class="form-control" data-ws-status>
								<option value="In Progress" ${currentStatus === "In Progress" ? "selected" : ""}>${__(
			"In Progress"
		)}</option>
								<option value="On Hold" ${currentStatus === "On Hold" ? "selected" : ""}>${__("On Hold")}</option>
								<option value="Blocked" ${currentStatus === "Blocked" ? "selected" : ""}>${__("Blocked")}</option>
								<option value="Archived" ${currentStatus === "Archived" ? "selected" : ""}>${__(
			"Archived"
		)}</option>
							</select>
						</div>
						<div class="okr-checkin-field">
							<label>${__("Date")}</label>
							<input class="form-control" type="date" data-ws-checkin-date value="${frappe.datetime.now_date()}">
						</div>
					</div>
					<label class="okr-update-field">${__(
						"Description / Update"
					)} <textarea class="form-control" rows="4" data-ws-update></textarea></label>
					<div class="okr-checkin-bottom-row">
						<div class="okr-attach-line"><div data-ws-attachment></div><button class="btn btn-sm btn-default" data-attach-file>${__(
							"Attach File"
						)}</button></div>
						<div class="okr-inline-actions"><button class="btn btn-sm btn-default" data-cancel-checkin>${__(
							"Cancel"
						)}</button><button class="btn btn-sm btn-dark" data-save-checkin>${__(
			"Save Check-In"
		)}</button></div>
					</div>
				</div>
			</div>
		`;
	}

	history_timeline(ai, kr, measurement) {
		const meas = measurement || this.get_effective_action_measurement(ai, kr);
		const rows = ai.history || [];
		const isCheckinOpen = this.state.action_checkin === ai.name;
		const checkinButton =
			ai.can_checkin && !isCheckinOpen
				? `<button type="button" class="btn btn-sm btn-primary-light okr-history-checkin" data-open-checkin="${
						ai.name
				  }">${__("+ Check-In")}</button>`
				: "";
		const historyHeader = `<div class="okr-history-head"><div class="okr-history-title">${__(
			"Check-In History"
		)}</div>${checkinButton}</div>`;
		if (!rows.length)
			return `<div class="okr-history">${historyHeader}<div class="okr-history-empty">${__(
				"No check-ins yet this sprint"
			)}</div></div>`;
		const showAll = Boolean(this.state.action_history_all[ai.name]);
		const visibleRows = showAll ? rows : rows.slice(0, 3);
		const historyToggle =
			rows.length > 3
				? `<button type="button" class="okr-history-more" data-toggle-all-history="${
						ai.name
				  }">${
						showAll ? __("Show Less") : __("View More ({0})", [rows.length - 3])
				  }</button>`
				: "";
		return `<div class="okr-history">${historyHeader}${visibleRows
			.map(
				(row) => `
                        <div class="okr-history-row">
                                <div class="okr-history-date"><span>${frappe.datetime.str_to_user(
									row.checkin_date
								)}</span>${
									row.delegated_by_name
										? `<small style="display:block;margin-top:2px;font-size:10px;color:#64748b;">${frappe.utils.escape_html(
												row.delegated_by_name
										  )}</small>`
										: ""
								}</div>
                                <p>
                                        <span class="okr-history-details">${frappe.utils.escape_html(
											row.achievements || ""
										)}${
					row.blockers
						? `<br><b>${__("Blocker")}:</b> ${frappe.utils.escape_html(row.blockers)}`
						: ""
				}</span>
                                        <span class="okr-history-meta">
                                                ${
													row.attachment
														? `<button type="button" class="okr-history-attachment" data-preview-attachment="${frappe.utils.escape_html(
																row.attachment
														  )}" title="${__(
																"View Attachment"
														  )}" aria-label="${__(
																"View Attachment"
														  )}">${frappe.utils.icon(
																"attachment",
																"sm"
														  )}</button>`
														: ""
												}
                                                <strong class="${
													row.action_status === "Blocked"
														? "is-blocked"
														: ""
												}">${this.format_checkin_value(row, meas)}</strong>
                                        </span>
                                </p>
                        </div>
                `
			)
			.join("")}${historyToggle}</div>`;
	}
	get_effective_action_measurement(ai, kr) {
		const isCustom = Boolean(ai && ai.customize_measurement);
		if (isCustom) {
			const metricType = ai.metric_type || "Percentage";
			const direction = ai.metric_direction || "Increase";
			const baseline = flt(ai.baseline_value || 0, 2);
			const target = flt(ai.target_value || 0, 2);
			const current = ai.current_value !== undefined && ai.current_value !== null ? flt(ai.current_value, 2) : baseline;
			let progress = flt(ai.progress || 0, 2);
			if (metricType === "Boolean") {
				progress = current ? 100.0 : 0.0;
			} else if (target !== baseline) {
				if (direction === "Decrease") {
					progress = ((baseline - current) / (baseline - target)) * 100.0;
				} else {
					progress = ((current - baseline) / (target - baseline)) * 100.0;
				}
				progress = Math.min(100.0, Math.max(0.0, Math.round(progress * 100) / 100));
			}
			return {
				is_custom: true,
				metric_type: metricType,
				metric_direction: direction,
				baseline_value: baseline,
				target_value: target,
				current_value: current,
				progress: progress,
				currency: "",
				unit_of_measure: "",
			};
		}

		return {
			is_custom: false,
			metric_type: kr ? (kr.metric_type || "Percentage") : "Percentage",
			metric_direction: kr ? (kr.metric_direction || "Increase") : "Increase",
			baseline_value: flt(kr ? kr.baseline_value : 0, 2),
			target_value: flt(kr ? kr.target_value : 0, 2),
			current_value: flt(kr ? kr.current_value : 0, 2),
			progress: flt(ai ? ai.progress : 0, 2),
			currency: kr ? (kr.currency || "") : "",
			unit_of_measure: kr ? (kr.unit_of_measure || "") : "",
		};
	}

	action_progress_display(ai, kr, measurement) {
		const meas = measurement || this.get_effective_action_measurement(ai, kr);
		const metricType = (meas.metric_type || "Percentage").toLowerCase();
		if (metricType === "percentage") {
			return `${this.format_kr_number(meas.progress)}%`;
		}
		const latest = (ai.history || [])[0];
		const value = latest && latest.current_value !== undefined && latest.current_value !== null
			? latest.current_value
			: meas.current_value;
		if (metricType === "currency") {
			return this.format_kr_currency(value, meas.currency);
		}
		const unit = (meas.unit_of_measure || "").trim();
		const display = this.format_kr_number(value);
		return unit && unit !== "%" ? `${display} ${frappe.utils.escape_html(unit)}` : display;
	}

	format_checkin_value(row, measurement_or_kr) {
		const metricType = ((measurement_or_kr && measurement_or_kr.metric_type) || "Percentage").toLowerCase();
		if (metricType === "currency")
			return this.format_kr_currency(row.current_value, measurement_or_kr.currency);
		if (metricType === "percentage") return `${this.format_kr_number(row.current_value)}%`;
		return this.format_kr_number(row.current_value);
	}

	kr_progress_display(kr) {
		const metricType = (kr.metric_type || "Percentage").toLowerCase();
		const unit = (kr.unit_of_measure || "").trim();
		if (this.is_task_kr(kr, unit)) {
			return `${this.format_kr_number(kr.completed_action_items)} / ${this.format_kr_number(
				kr.total_action_items
			)}`;
		}
		if (metricType === "percentage") {
			return `${this.format_kr_number(kr.target_progress || kr.current_value || 0)}%`;
		}
		if (metricType === "currency") {
			return `${this.format_kr_currency(
				kr.current_value,
				kr.currency
			)} / ${this.format_kr_currency(kr.target_value, kr.currency)}`;
		}

		const value = `${this.format_kr_number(kr.current_value)} / ${this.format_kr_number(
			kr.target_value
		)}`;
		return unit && unit !== "%" ? `${value} ${unit}` : value;
	}

	is_task_kr(kr, unit) {
		const normalizedUnit = (unit || "").toLowerCase();
		return (
			cint(kr.total_action_items || 0) > 0 &&
			/action items?|tasks?|to-dos?|todos?/.test(normalizedUnit)
		);
	}

	format_kr_number(value) {
		const number = flt(value || 0, 2);
		if (Math.abs(number - Math.round(number)) < 0.005) {
			return Math.round(number).toLocaleString();
		}
		return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
	}

	format_kr_currency(value, currency) {
		if (typeof format_currency === "function") {
			const number = flt(value || 0, 2);
			const decimals = Math.abs(number - Math.round(number)) < 0.005 ? 0 : 2;
			return format_currency(number, currency, decimals);
		}
		return this.format_kr_number(value);
	}

	context(label, value) {
		return `<div><span>${label}</span><strong>${frappe.utils.escape_html(
			value || "-"
		)}</strong></div>`;
	}
	no_actions() {
		return `<div class="okr-no-actions">${__("No action items under this Key Result.")}</div>`;
	}
	empty_state() {
		return `<div class="okr-empty-workspace"><div class="okr-empty-icon">◎</div><h3>${__(
			"No OKRs found"
		)}</h3><p>${__(
			"No objectives match the current filter. Try a different plan, level, or owner."
		)}</p><button class="btn btn-primary" data-adjust-filter>${__(
			"Adjust Filter"
		)}</button></div>`;
	}

	is_kr_blocked(kr) {
		if (kr.status === "Blocked") return true;
		if ((kr.action_items || []).some((ai) => ai.status === "Blocked")) return true;
		return false;
	}

	is_kr_at_risk(kr, todayStr) {
		if (kr.status === "At Risk") return true;
		const today = moment(todayStr);
		if (kr.end_date) {
			const diffDays = moment(kr.end_date).diff(today, "days");
			const progress = flt(kr.target_progress || 0);
			if (diffDays >= 0 && diffDays <= 14 && progress < 70) return true;
		}
		if (
			(kr.action_items || []).some((ai) => {
				if (ai.status === "At Risk") return true;
				if (ai.due_date) {
					const due = moment(ai.due_date);
					const isOverdue = due.isBefore(today, "day");
					const isCompleted =
						ai.status === "Completed" ||
						ai.status === "Archived" ||
						flt(ai.progress || 0) >= 100;
					if (isOverdue && !isCompleted) return true;

					const diffDays = due.diff(today, "days");
					const progress = flt(ai.progress || 0);
					if (diffDays >= 0 && diffDays <= 14 && progress < 70) return true;
				}
				return false;
			})
		) {
			return true;
		}
		return false;
	}

	initials(value) {
		if (!value) return "?";
		const namePart = value.includes("@") ? value.split("@")[0] : value;
		const parts = namePart.trim().split(/[\s.]+/);
		return parts
			.map((p) => p[0])
			.join("")
			.toUpperCase()
			.slice(0, 2);
	}

	toggle(group, key) {
		this.state[group][key] = !this.state[group][key];
		this.render_content();
	}
	open_checkin(action) {
		this.state.action_checkin = this.state.action_checkin === action ? null : action;
		this.attachment = "";
		this.render_content();
	}

	attach_file() {
		new frappe.ui.FileUploader({
			allow_multiple: false,
			on_success: (file) => {
				this.attachment = file.file_url;
				this.render_attachment();
			},
		});
	}

	render_attachment() {
		const html = this.attachment
			? `<div class="okr-file-chip"><span>${frappe.utils.escape_html(
					this.attachment.split("/").pop()
			  )}</span><button class="btn btn-xs btn-link" data-remove-attachment>${__(
					"Remove"
			  )}</button></div>`
			: `<span class="text-muted small">${__("Optional proof file")}</span>`;
		this.$body.find("[data-ws-attachment]").html(html);
	}

	save_checkin() {
		if (this.saving_checkin) return;

		const action = this.state.action_checkin;
		const $panel = this.$body.find(".okr-inline-checkin");
		const $button = $panel.find("[data-save-checkin]");
		const $value = $panel.find("[data-ws-progress]");
		const currentValue = flt($value.val(), 2);
		const minimum = flt($value.attr("min"), 2);
		const maximum = flt($value.attr("max"), 2);
		const update = ($panel.find("[data-ws-update]").val() || "").trim();
		const checkinDate = ($panel.find("[data-ws-checkin-date]").val() || "").trim();
		const args = {
			action_item: action,
			current_value: currentValue,
			status: ($panel.find("[data-ws-status]").val() || "").trim(),
			update,
			checkin_date: checkinDate,
			blocker: "",
			dependency: "",
			attachment: this.attachment || "",
		};

		if (!action) return frappe.msgprint(__("Please select an Action Item."));
		if (isNaN(currentValue) || currentValue < minimum || currentValue > maximum)
			return frappe.msgprint(
				__("Current value must be between {0} and {1}.", [minimum, maximum])
			);

		this.saving_checkin = true;
		$button.prop("disabled", true).text(__("Saving..."));

		frappe.call({
			method: "okr_management.okr_management.page.okr_workspace.okr_workspace.save_workspace_checkin",
			args,
			freeze: true,
			freeze_message: __("Saving Check-In..."),
			callback: (r) => {
				this.saving_checkin = false;
				$button.prop("disabled", false).text(__("Save Check-In"));
				if (r.exc) return;

				const message =
					r.message && r.message.name
						? __("Check-In saved: {0}", [r.message.name])
						: __("Check-In saved");
				frappe.show_alert({ message, indicator: "green" });
				this.state.action_history[action] = true;
				this.state.action_checkin = null;
				this.attachment = "";
				this.load();
			},
			error: () => {
				this.saving_checkin = false;
				$button.prop("disabled", false).text(__("Save Check-In"));
			},
		});
	}


	save_measurement() {
		const action = this.state.measurement_action;
		const $panel = this.$body.find(`[data-measurement-action="${action}"]`);
		const $button = $panel.find("[data-save-measurement]");
		const args = {
			action_item: action,
			metric_type: $panel.find("[data-measurement-type]").val(),
			metric_direction: $panel.find("[data-measurement-direction]").val(),
			baseline_value: flt($panel.find("[data-measurement-baseline]").val(), 2),
			target_value: flt($panel.find("[data-measurement-target]").val(), 2),
			current_value: flt($panel.find("[data-measurement-current]").val(), 2),
		};
		if (!action || !$panel.length) return;
		const lower = Math.min(args.baseline_value, args.target_value);
		const upper = Math.max(args.baseline_value, args.target_value);
		if (args.metric_type !== "Boolean" && (args.current_value < lower || args.current_value > upper)) {
			frappe.msgprint(__("Current Value must be between {0} and {1}.", [lower, upper]));
			return;
		}
		$button.prop("disabled", true).text(__("Saving..."));
		frappe.call({
			method: "okr_management.okr_management.page.okr_workspace.okr_workspace.save_action_measurement",
			args,
			freeze: true,
			freeze_message: __("Saving Measurement..."),
			callback: (r) => {
				$button.prop("disabled", false).text(__("Save Measurement"));
				if (r.exc) return;
				frappe.show_alert({ message: __("Measurement updated"), indicator: "green" });
				this.state.measurement_action = null;
				this.load();
			},
			error: () => $button.prop("disabled", false).text(__("Save Measurement")),
		});
	}

	get_assignee_name(email) {
		if (!email) return "";
		let name = "";
		if (window.frappe && frappe.user_info) {
			const info = frappe.user_info(email);
			if (info && info.fullname) name = info.fullname;
		}
		if (
			!name &&
			window.frappe &&
			frappe.boot &&
			frappe.boot.user_info &&
			frappe.boot.user_info[email]
		) {
			name = frappe.boot.user_info[email].fullname;
		}
		if (!name) {
			if (email.includes("@")) {
				const username = email.split("@")[0];
				name = username
					.split(/[\._-]/)
					.map((s) => s.charAt(0).toUpperCase() + s.slice(1))
					.join(" ");
			} else {
				name = email;
			}
		}
		return name;
	}
}
