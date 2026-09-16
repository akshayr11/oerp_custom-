// Payment Entry: restrict the Reference Doc No (custom_reference_doc_no)
// link field to only show submitted Purchase Advance Requests.

frappe.ui.form.on("Payment Entry", {
	setup(frm) {
		frm.set_query("custom_reference_doc_no", () => {
			return {
				filters: {
					docstatus: 1,
				},
			};
		});
	},
});
