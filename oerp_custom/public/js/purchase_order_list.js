// Purchase Order list: paperclip badge on every row showing ALL attachments,
// including files attached item-wise (Attach fields on the items table).
//
// Why not `formatters`/`onload`: the subject column ignores custom formatters,
// and onload fires before the rows exist. Instead the rows are decorated in the
// DOM after every render, from one batched server call.

frappe.listview_settings["Purchase Order"] = {
	refresh(listview) {
		decorate_attachments(listview);

		// "Load More" appends rows without firing refresh — wrap render_list
		// once so decoration re-runs after every render.
		if (!listview._attach_patch) {
			listview._attach_patch = true;
			const original = listview.render_list.bind(listview);
			listview.render_list = function (...args) {
				const out = original(...args);
				decorate_attachments(listview);
				return out;
			};
		}
	},
};

function decorate_attachments(listview) {
	const names = (listview.data || []).map((d) => d.name);
	if (!names.length) return;

	frappe.call({
		method: "oerp_custom.api.get_po_attachments",
		args: { po_names: names },
		callback({ message }) {
			if (!message) return;
			render_badges(listview, message);
		},
	});
}

function render_badges(listview, info) {
	listview.$result.find(".list-row-container").each(function () {
		const $row = $(this);
		const name = $row.find(".list-row-checkbox").attr("data-name");
		if (!name || !info[name]) return;

		$row.find(".oerp-attach-badge").remove();

		const total = info[name].total;
		if (!total) return;

		const $badge = $(
			`<span class="oerp-attach-badge" title="${__("View attachments")}"
				style="cursor:pointer; margin-left:8px; padding:1px 8px; border-radius:10px;
				background: var(--bg-light-gray, #f3f3f3); color: var(--text-muted); font-size:11px;
				white-space:nowrap;">
				${frappe.utils.icon("attachment", "sm")} ${total}
			</span>`
		);

		$badge.on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			show_attachment_dialog(name, info[name].files);
		});

		// place right after the document name link
		const $subject = $row.find(".list-subject .level-item.bold, .list-subject a").first();
		($subject.length ? $subject : $row.find(".list-subject")).after($badge);
	});
}

function show_attachment_dialog(po_name, files) {
	const order_files = files.filter((f) => !f.item_code);
	const item_files = files.filter((f) => f.item_code);

	const link = (f) =>
		`<a href="${f.file_url}" target="_blank" rel="noopener">
			${frappe.utils.icon("attachment", "sm")} ${frappe.utils.escape_html(f.file_name)}
		</a>`;

	let html = "";

	if (order_files.length) {
		html += `<div class="text-muted small" style="margin-bottom:4px">${__("Attached on the order")}</div>`;
		html += `<ul style="padding-left:18px; margin-bottom:12px">${order_files
			.map((f) => `<li style="margin:3px 0">${link(f)}</li>`)
			.join("")}</ul>`;
	}

	if (item_files.length) {
		const by_item = {};
		item_files.forEach((f) => {
			const key = `${__("Row")} ${f.item_row} — ${f.item_code}`;
			(by_item[key] = by_item[key] || []).push(f);
		});
		html += `<div class="text-muted small" style="margin-bottom:4px">${__("Attached item-wise")}</div>`;
		Object.keys(by_item).forEach((key) => {
			html += `<div style="font-weight:600; margin:6px 0 2px">${frappe.utils.escape_html(key)}</div>`;
			html += `<ul style="padding-left:18px; margin-bottom:6px">${by_item[key]
				.map((f) => `<li style="margin:3px 0">${link(f)}</li>`)
				.join("")}</ul>`;
		});
	}

	if (!html) html = `<div class="text-muted">${__("No attachments.")}</div>`;

	const d = new frappe.ui.Dialog({
		title: __("Attachments — {0}", [po_name]),
		fields: [{ fieldname: "body", fieldtype: "HTML", options: html }],
		primary_action_label: __("Open Order"),
		primary_action() {
			d.hide();
			frappe.set_route("Form", "Purchase Order", po_name);
		},
	});
	d.show();
}
