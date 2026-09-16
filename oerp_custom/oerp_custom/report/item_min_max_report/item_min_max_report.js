// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.query_reports["Item Min Max Report"] = {
	filters: [
		{
			fieldname: "warehouse",
			label: __("Store"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "item_group",
			label: __("Item Category"),
			fieldtype: "Link",
			options: "Item Group",
		},
	],
};
