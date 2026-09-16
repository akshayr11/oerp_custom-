// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.query_reports["SI-GRV Monthly Summary"] = {
	filters: [
		{
			fieldname: "year",
			label: "Year",
			fieldtype: "Select",
			options: ["2023", "2024", "2025", "2026", "2027"],
			default: String(new Date().getFullYear()),
			reqd: 1,
		},
		{
			fieldname: "months",
			label: "Month",
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				let months = [
					"January", "February", "March", "April", "May", "June",
					"July", "August", "September", "October", "November", "December",
				];
				return months
					.filter((m) => m.toLowerCase().includes((txt || "").toLowerCase()))
					.map((m) => ({ value: m, description: "" }));
			},
			reqd: 1,
		},
	],
};
