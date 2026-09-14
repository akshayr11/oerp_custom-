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
//
// NOTE: console.log/console.warn lines below are temporary diagnostics for
// tracking down why Cost Center isn't backfilling on some pulled-in rows.
// Safe to remove once confirmed working.

frappe.ui.form.on('Request for Quotation', {
    refresh: function(frm) {
        console.log('[RFQ] refresh fired, backfilling cost centers...');
        backfill_all_cost_centers(frm);

        // --- SQ Comparison button (submitted RFQs only) ---
        if (frm.doc.docstatus === 1) {
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
    },

    items_add: function(frm, cdt, cdn) {
        console.log('[RFQ] items_add fired for row:', cdn);
        fetch_cost_center(frm, cdt, cdn);
    },

    company: function(frm) {
        // if company changes, re-check rows missing a cost center
        backfill_all_cost_centers(frm);
    }
});

frappe.ui.form.on('Request for Quotation Item', {
    material_request_item: function(frm, cdt, cdn) {
        console.log('[RFQ] material_request_item field changed on row:', cdn);
        fetch_cost_center(frm, cdt, cdn);
    }
});

function fetch_cost_center(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    console.log(
        '[RFQ] Checking row:', row.name,
        '| item_code:', row.item_code,
        '| material_request:', row.material_request,
        '| material_request_item:', row.material_request_item,
        '| existing custom_cost_center:', row.custom_cost_center
    );

    if (!row.material_request_item) {
        console.warn('[RFQ] No material_request_item on this row — cannot look up source Cost Center. Skipping.');
        return;
    }

    if (row.custom_cost_center) {
        console.log('[RFQ] Row already has a Cost Center. Skipping.');
        return;
    }

    frappe.db.get_value('Material Request Item', row.material_request_item, 'cost_center')
        .then((r) => {
            console.log('[RFQ] get_value(Material Request Item) result:', r);
            const mr_cost_center = r && r.message ? r.message.cost_center : null;

            if (mr_cost_center) {
                frappe.model.set_value(cdt, cdn, 'custom_cost_center', mr_cost_center);
                console.log('[RFQ] Set custom_cost_center to:', mr_cost_center);
            } else {
                console.log('[RFQ] Material Request Item has no cost_center, falling back to Company default.');
                apply_default_company_cost_center(frm, cdt, cdn);
            }
        })
        .catch((err) => {
            console.error('[RFQ] get_value failed (Material Request Item):', err);
        });
}

function apply_default_company_cost_center(frm, cdt, cdn) {
    if (!frm.doc.company) {
        console.warn('[RFQ] No Company set on RFQ, cannot apply default Cost Center.');
        return;
    }

    frappe.db.get_value('Company', frm.doc.company, 'cost_center')
        .then((r) => {
            console.log('[RFQ] get_value(Company) result:', r);
            const default_cc = r && r.message ? r.message.cost_center : null;
            if (default_cc) {
                frappe.model.set_value(cdt, cdn, 'custom_cost_center', default_cc);
                console.log('[RFQ] Set custom_cost_center to Company default:', default_cc);
            } else {
                console.warn('[RFQ] Company has no default Cost Center either. Row stays blank.');
            }
        })
        .catch((err) => {
            console.error('[RFQ] get_value failed (Company default cost center):', err);
        });
}

function backfill_all_cost_centers(frm) {
    console.log('[RFQ] Backfilling', (frm.doc.items || []).length, 'row(s)...');
    (frm.doc.items || []).forEach((row) => {
        fetch_cost_center(frm, row.doctype, row.name);
    });
}