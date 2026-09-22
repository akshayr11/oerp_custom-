// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Receipt Voucher", {
	setup(frm) {
		frm.set_query("equipment_timesheet", () => {
			return { filters: { workflow_state: "Approved", docstatus: 1 } };
		});
	},
});
