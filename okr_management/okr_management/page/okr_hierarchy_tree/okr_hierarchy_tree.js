frappe.pages['okr-hierarchy-tree'].on_page_load = function(wrapper) {
	new OKRHierarchyTree(wrapper);
};

class OKRHierarchyTree {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('OKR Hierarchy Tree'),
			single_column: true,
		});
		this.page.set_primary_action(__('Refresh'), () => this.refresh(), 'refresh');
		this.$body = $('<div class="okr-hierarchy-tree"></div>').appendTo(this.page.main);
		this.refresh();
	}

	refresh() {
		this.$body.html(`<div class="text-muted">${__('Loading OKR hierarchy...')}</div>`);
		frappe.call({
			method: 'okr_management.hierarchy.get_okr_hierarchy_tree',
			callback: (r) => this.render(r.message || []),
			error: () => this.$body.html(`<div class="alert alert-danger">${__('Unable to load OKR hierarchy.')}</div>`),
		});
	}

	render(nodes) {
		if (!nodes.length) {
			this.$body.html(`<div class="alert alert-info">${__('No OKR hierarchy found for your permissions.')}</div>`);
			return;
		}
		this.$body.html(`
			<style>
				.okr-tree-toolbar { margin-bottom: 12px; display:flex; gap:8px; }
				.okr-tree-node { margin: 6px 0 6px 18px; }
				.okr-tree-row { display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid var(--border-color); border-radius:10px; background:var(--card-bg); }
				.okr-tree-row .toggle { width:22px; height:22px; border:0; background:var(--bg-light-gray); border-radius:6px; }
				.okr-tree-row .toggle.empty { visibility:hidden; }
				.okr-tree-row .title { font-weight:600; }
				.okr-tree-meta { color:var(--text-muted); font-size:12px; margin-left:auto; text-align:right; }
				.okr-tree-pill { font-size:11px; padding:2px 7px; border-radius:999px; background:var(--bg-light-gray); color:var(--text-muted); white-space:nowrap; }
				.okr-tree-children.collapsed { display:none; }
			</style>
			<div class="okr-tree-toolbar">
				<button class="btn btn-sm btn-default expand-all">${__('Expand All')}</button>
				<button class="btn btn-sm btn-default collapse-all">${__('Collapse All')}</button>
			</div>
			<div class="okr-tree-root">${nodes.map(node => this.node(node)).join('')}</div>
		`);
		this.bind();
	}

	node(node) {
		const children = node.children || [];
		const hasChildren = children.length > 0;
		const route = this.route(node);
		return `<div class="okr-tree-node">
			<div class="okr-tree-row">
				<button class="toggle ${hasChildren ? '' : 'empty'}" data-toggle>${hasChildren ? '▾' : ''}</button>
				<span class="okr-tree-pill">${this.esc(node.type)}</span>
				<a class="title" href="${route}">${this.esc(node.title || node.name)}</a>
				<span class="text-muted small">${this.esc(node.name || '')}</span>
				<div class="okr-tree-meta">${this.meta(node)}</div>
			</div>
			${hasChildren ? `<div class="okr-tree-children">${children.map(child => this.node(child)).join('')}</div>` : ''}
		</div>`;
	}

	meta(node) {
		const parts = [];
		if (node.department) parts.push(node.department);
		if (node.owner) parts.push(__('Owner') + ': ' + node.owner);
		if (node.status) parts.push(node.status);
		if (node.progress !== undefined && node.progress !== null) parts.push(node.progress + '%');
		if (node.priority) parts.push(node.priority);
		return parts.map(part => this.esc(part)).join(' · ');
	}

	route(node) {
		const routeMap = {
			'OKR Cycle': 'okr-cycle',
			'OKR Objective': 'okr-objective',
			'OKR Key Result': 'okr-key-result',
			'OKR Action Item': 'okr-action-item',
		};
		return `/app/${routeMap[node.doctype] || frappe.router.slug(node.doctype || '')}/${encodeURIComponent(node.name || '')}`;
	}

	bind() {
		this.$body.find('[data-toggle]').on('click', function() {
			const $children = $(this).closest('.okr-tree-node').children('.okr-tree-children');
			$children.toggleClass('collapsed');
			$(this).text($children.hasClass('collapsed') ? '▸' : '▾');
		});
		this.$body.find('.expand-all').on('click', () => {
			this.$body.find('.okr-tree-children').removeClass('collapsed');
			this.$body.find('[data-toggle]:not(.empty)').text('▾');
		});
		this.$body.find('.collapse-all').on('click', () => {
			this.$body.find('.okr-tree-children').addClass('collapsed');
			this.$body.find('[data-toggle]:not(.empty)').text('▸');
		});
	}

	esc(value) {
		return frappe.utils.escape_html(value == null ? '' : String(value));
	}
}
