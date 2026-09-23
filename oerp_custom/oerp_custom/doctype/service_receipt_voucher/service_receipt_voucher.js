// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Receipt Voucher", {
	setup(frm) {
		// Only a live (submitted, not cancelled) contract has timesheets
		// worth pulling in.
		frm.set_query("hiring_contract", () => {
			return { filters: { docstatus: 1 } };
		});

		frm.set_query("timesheet", "timesheets", () => {
			return {
				query: "oerp_custom.overrides.service_receipt_voucher.timesheet_query",
				filters: {
					hiring_contract: frm.doc.hiring_contract,
					service_month: frm.doc.service_month,
					service_year: frm.doc.service_year,
				},
			};
		});

		frm.set_query("equipment", "timesheets", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return {
				query: "oerp_custom.overrides.service_receipt_voucher.equipment_in_timesheet_query",
				filters: { timesheet: row.timesheet },
			};
		});
	},
});

frappe.ui.form.on("Service Receipt Voucher Timesheet", {
	timesheet(frm, cdt, cdn) {
		// A new timesheet invalidates whatever equipment was picked before.
		frappe.model.set_value(cdt, cdn, "equipment", null);
	},

	equipment(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.timesheet || !row.equipment || !frm.doc.hiring_contract) {
			return;
		}

		frappe.call({
			method: "oerp_custom.overrides.service_receipt_voucher.get_row_details",
			args: {
				hiring_contract: frm.doc.hiring_contract,
				timesheet: row.timesheet,
				equipment: row.equipment,
			},
			callback(r) {
				const data = r.message;
				if (!data) {
					return;
				}
				const current = locals[cdt][cdn];
				if (!current || current.timesheet !== row.timesheet || current.equipment !== row.equipment) {
					// row moved on while the call was in flight
					return;
				}
				Object.entries(data).forEach(([fieldname, value]) => {
					frappe.model.set_value(cdt, cdn, fieldname, value);
				});
				update_totals(frm);
			},
		});
	},
});

function update_totals(frm) {
	const totals = (frm.doc.timesheets || []).reduce(
		(acc, row) => {
			acc.amount += flt(row.amount);
			acc.vat += flt(row.vat_amount);
			return acc;
		},
		{ amount: 0, vat: 0 }
	);

	frm.set_value("total_amount", totals.amount);
	frm.set_value("total_vat_amount", totals.vat);
	frm.set_value("grand_total", totals.amount + totals.vat);
}
