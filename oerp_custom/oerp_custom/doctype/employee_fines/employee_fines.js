// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

// Same "Vehicle/Equipment Hiring" Item Group convention used to filter the
// Equipment/Asset link everywhere else in this app (Fleet Hiring Request).
const EQUIPMENT_ITEM_GROUP = "Vehicle/Equipment Hiring";

frappe.ui.form.on("Employee Fines", {
	setup(frm) {
		frm.set_query("equipment", () => {
			return {
				filters: {
					item_group: EQUIPMENT_ITEM_GROUP,
					is_stock_item: 0,
					disabled: 0,
				},
			};
		});
	},
});
