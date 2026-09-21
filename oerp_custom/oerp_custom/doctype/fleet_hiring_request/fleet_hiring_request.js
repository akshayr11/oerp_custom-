// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

// Equipment rows only offer service items filed under the
// "Vehicle and Equipment Hiring" Item Group — same is_stock_item = 0
// convention Material Request uses for its own service-item filtering.
const EQUIPMENT_ITEM_GROUP = "Vehicle and Equipment Hiring";

frappe.ui.form.on("Fleet Hiring Request", {
	setup(frm) {
		set_equipment_filter(frm);
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value("requested_by", frappe.session.user);
		}
	},

	refresh(frm) {
		if (frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(__("Hiring Contract"), () => {
				frappe.model.open_mapped_doc({
					method: "oerp_custom.overrides.fleet_hiring_request.create_hiring_contract",
					frm: frm,
				});
			}, __("Create"));
		}
	},
});

function set_equipment_filter(frm) {
	frm.set_query("equipment", "equipment", () => {
		return {
			filters: {
				item_group: EQUIPMENT_ITEM_GROUP,
				is_stock_item: 0,
				disabled: 0,
			},
		};
	});
}
