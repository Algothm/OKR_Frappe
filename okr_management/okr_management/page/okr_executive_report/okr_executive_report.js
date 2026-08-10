frappe.pages['okr-executive-report'].on_page_load = function (wrapper) {
	new OKRExecutiveReport(wrapper);
};

class OKRExecutiveReport {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('OKR Executive Report'),
			single_column: true,
			card_layout: true,
		});
		this.$body = $(`<div class="okr-executive-report-page"></div>`).appendTo(this.page.main);
		this.load_report();
	}

	load_report() {
		// Show actions immediately so user isn't stuck with a blank toolbar
		this.render_actions();
		this.$body.html(`
			<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 24px;gap:14px;color:var(--text-muted);">
				<div style="width:36px;height:36px;border:3px solid var(--border-color);border-top-color:var(--primary);border-radius:50%;animation:okr-report-spin 0.8s linear infinite;"></div>
				<div style="font-size:14px;">${__('Generating executive report preview…')}</div>
				<style>@keyframes okr-report-spin { to { transform: rotate(360deg); } }</style>
			</div>
		`);

		frappe.call({
			method: 'okr_management.insights.get_executive_report_preview',
			callback: (r) => {
				const message = r.message || {};
				this.$body.html(message.html || `<div class="alert alert-warning" style="margin:24px;">${__('No report data found. Please generate demo data first.')}</div>`);
				// Update title with company if available
				if (message.title) {
					this.page.set_title(message.title);
				}
			},
			error: () => {
				this.$body.html(`
					<div style="padding:24px;">
						<div class="alert alert-danger">
							<b>${__('Unable to load executive report preview.')}</b>
							<p style="margin:8px 0 0;font-size:13px;">${__('Check that OKR data exists and server is running.')}</p>
						</div>
						<button class="btn btn-default" style="margin-top:12px;" onclick="frappe.set_route('okr-executive-attention')">
							← ${__('Go to Executive Attention')}
						</button>
					</div>
				`);
			},
		});
	}

	render_actions() {
		this.page.clear_actions();
		this.page.set_primary_action(__('Print'), () => {
			// Print only the report content, not the Frappe chrome
			window.print();
		}, 'printer');
		this.page.set_secondary_action(__('Refresh'), () => this.load_report(), 'refresh');
		this.page.add_action_item(__('Download PDF'), () => this.download_pdf());
		this.page.add_action_item(__('← Executive Attention'), () => frappe.set_route('okr-executive-attention'));
	}

	download_pdf() {
		frappe.show_alert({message: __('Generating PDF…'), indicator: 'blue'}, 3);
		const url = frappe.urllib.get_full_url('/api/method/okr_management.insights.download_executive_report_pdf');
		window.open(url, '_blank', 'noopener');
	}
}
