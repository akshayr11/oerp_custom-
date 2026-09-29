// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Equipment Certificate", {
	setup(frm) {
		frm.set_query("certificate_type", () => {
			return { filters: { current_status: "Active" } };
		});
	},

	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Renewal"), () => {
				frappe.new_doc("Equipment Certificate Renewal", { equipment: frm.doc.equipment }, (doc) => {
					const row = frappe.model.add_child(doc, "Equipment Certificate Renewal Detail", "renewals");
					row.equipment_certificate = frm.doc.name;
				});
			}, __("Create"));
		}
	},

	certificate_type(frm) {
		suggest_expiry_date(frm);
	},

	issue_date(frm) {
		suggest_expiry_date(frm);
	},
});

function suggest_expiry_date(frm) {
	if (!(frm.doc.certificate_type && frm.doc.issue_date)) {
		return;
	}
	frappe.call({
		method: "oerp_custom.overrides.equipment_certificate.get_expiry_date",
		args: { certificate_type: frm.doc.certificate_type, issue_date: frm.doc.issue_date },
		callback(r) {
			if (r.message) {
				frm.set_value("expiry_date", r.message);
			}
		},
	});
}
