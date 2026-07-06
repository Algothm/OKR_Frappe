frappe.pages['okr-analytics'].on_page_load = function(wrapper) {
	new OKRAnalytics(wrapper);
};

class OKRAnalytics {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('OKR Analytics'),
			single_column: true
		});
		this.$body = $(`<div class="okr-analytics" style="padding: 24px;"></div>`).appendTo(this.page.main);
		this.render();
	}

	render() {
		this.$body.html(`
			<div class="alert alert-info" style="border-radius: 8px;">
				<h4 style="margin-top: 0;">${__('OKR Analytics Dashboard')}</h4>
				<p style="margin-bottom: 0;">${__('This is a placeholder page for OKR Analytics.')}</p>
			</div>
		`);
	}
}
