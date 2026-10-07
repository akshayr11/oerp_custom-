// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.query_reports["MRF Status by Cost Center"] = {
	filters: [
		{
			fieldname: "cost_center",
			label: "Cost Center",
			fieldtype: "Link",
			options: "Cost Center",
			reqd: 0,
		},
	],
};
