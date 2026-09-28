// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Equipment Certificate Renewal", {
	new_issue_date(frm) {
		suggest_new_expiry_date(frm);
	},
});

function suggest_new_expiry_date(frm) {
	if (!(frm.doc.certificate_type && frm.doc.new_issue_date)) {
		return;
	}
	frappe.call({
		method: "oerp_custom.overrides.equipment_certificate.get_expiry_date",
		args: { certificate_type: frm.doc.certificate_type, issue_date: frm.doc.new_issue_date },
		callback(r) {
			if (r.message) {
				frm.set_value("new_expiry_date", r.message);
			}
		},
	});
}
