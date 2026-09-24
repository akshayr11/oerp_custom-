// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

// No manual "Create Purchase Order" button — the Hiring Contract's own
// on_submit hook (oerp_custom.oerp_custom.doctype.hiring_contract.hiring_contract)
// creates and submits the PO automatically the moment the Approve
// transition submits this document. Nothing to trigger from the form.

frappe.ui.form.on("Hiring Contract", {
	refresh(frm) {
		update_contract_value(frm);

		if (frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(__("Equipment Timesheet"), () => {
				frappe.new_doc("Equipment Timesheet", {
					hiring_contract: frm.doc.name,
					fleet_hiring_request: frm.doc.fleet_hiring_request,
				});
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
