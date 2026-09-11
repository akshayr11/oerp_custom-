// Client Script
// Doctype: Request for Quotation
// Setup:
// 1. Go to Client Script (list view) -> New
// 2. Doctype: Request for Quotation
// 3. Enabled: checked
// 4. Paste the code below into the "Script" field
// 5. Save
//
// Requires oerp_custom/oerp_custom/overrides/rfq.py to be in place
// with create_sq_comparison_from_rfq and get_approved_supplier_quotations
// (both @frappe.whitelist()).

frappe.ui.form.on('Request for Quotation', {
    refresh: function(frm) {
        if (frm.doc.docstatus !== 1) return;

        frappe.call({
            method: 'oerp_custom.oerp_custom.overrides.rfq.get_approved_supplier_quotations',
            args: { rfq: frm.doc.name }
        }).then(r => {
            if (r.message) {
                frm.add_custom_button('SQ Comparison', function() {
                    frappe.call({
                        method: 'oerp_custom.oerp_custom.overrides.rfq.create_sq_comparison_from_rfq',
                        args: { rfq: frm.doc.name },
                        freeze: true,
                        freeze_message: 'Creating SQ Comparison...'
                    }).then(res => {
                        if (res.message) {
                            frappe.set_route('Form', 'SQ Comparison', res.message);
                        }
                    });
                });
            }
        });
    }
});