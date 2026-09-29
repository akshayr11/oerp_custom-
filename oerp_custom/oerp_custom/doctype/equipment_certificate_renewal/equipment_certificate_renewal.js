// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Equipment Certificate Renewal", {
	setup(frm) {
		frm.set_query("equipment_certificate", "renewals", () => {
			return { filters: { equipment: frm.doc.equipment } };
		});
	},

	equipment(frm) {
		// A new Equipment invalidates whatever certificates were already
		// picked for the old one.
		(frm.doc.renewals || []).forEach((row) => {
			frappe.model.set_value(row.doctype, row.name, "equipment_certificate", null);
		});
	},
});

frappe.ui.form.on("Equipment Certificate Renewal Detail", {
	new_issue_date(frm, cdt, cdn) {
		suggest_new_expiry_date(frm, cdt, cdn);
	},

	certificate_type(frm, cdt, cdn) {
		suggest_new_expiry_date(frm, cdt, cdn);
	},
});

function suggest_new_expiry_date(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!(row.certificate_type && row.new_issue_date)) {
		return;
	}
	frappe.call({
		method: "oerp_custom.overrides.equipment_certificate.get_expiry_date",
		args: { certificate_type: row.certificate_type, issue_date: row.new_issue_date },
		callback(r) {
			if (r.message) {
				frappe.model.set_value(cdt, cdn, "new_expiry_date", r.message);
			}
		},
	});
}
