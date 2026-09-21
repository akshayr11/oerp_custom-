// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hiring Contract", {
	refresh(frm) {
		update_contract_value(frm);

		if (frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(__("Purchase Order"), () => {
				frappe.confirm(
					__("This will create and submit a Purchase Order directly. Continue?"),
					() => {
						frappe.call({
							method: "oerp_custom.overrides.hiring_contract.create_purchase_order",
							args: { source_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating Purchase Order..."),
							callback(r) {
								if (r.message) {
									frappe.set_route("Form", "Purchase Order", r.message);
								}
							},
						});
					}
				);
			}, __("Create"));
		}
	},
});

frappe.ui.form.on("Hiring Contract Item", {
	rate(frm, cdt, cdn) {
		update_row_amount(frm, cdt, cdn);
	},
	qty(frm, cdt, cdn) {
		update_row_amount(frm, cdt, cdn);
	},
	items_remove(frm) {
		update_contract_value(frm);
	},
});

function update_row_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const amount = flt(row.rate) * flt(row.qty);
	frappe.model.set_value(cdt, cdn, "amount", amount);
	update_contract_value(frm);
}

function update_contract_value(frm) {
	const total = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.amount), 0);
	frm.set_value("contract_value", total);
}
