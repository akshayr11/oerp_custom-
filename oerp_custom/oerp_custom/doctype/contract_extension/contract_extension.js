// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Extension", {
	setup(frm) {
		// Only a live (submitted, not cancelled) contract can be extended.
		frm.set_query("hiring_contract", () => {
			return { filters: { docstatus: 1 } };
		});
	},
});
