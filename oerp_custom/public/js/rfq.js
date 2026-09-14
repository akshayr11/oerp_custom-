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
// with create_sq_comparison_from_rfq, get_approved_supplier_quotations, and
// get_material_request_item_cost_center (all @frappe.whitelist()).
//
// Cost Center backfill uses a server call (not frappe.db.get_value) because
// Material Request Item is a child table with no independent Role
// Permission entries — the client-side get_value endpoint silently strips
// fields like cost_center for non-Administrator roles. The server-side
// frappe.db.get_value used in get_material_request_item_cost_center is a
// raw DB read with no such filtering.

frappe.ui.form.on('Request for Quotation', {
    refresh: function(frm) {
        backfill_all_cost_centers(frm);

        // --- SQ Comparison button (submitted RFQs only) ---
        if (frm.doc.docstatus === 1) {
            frappe.call({
                method: 'oerp_custom.overrides.rfq.get_approved_supplier_quotations',
                args: { rfq: frm.doc.name }
            }).then(r => {
                if (r.message) {
                    frm.add_custom_button('SQ Comparison', function() {
                        frappe.call({
                            method: 'oerp_custom.overrides.rfq.create_sq_comparison_from_rfq',
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
        fetch_cost_center(frm, cdt, cdn);
    },

    company: function(frm) {
        // if company changes, re-check rows missing a cost center
        backfill_all_cost_centers(frm);
    }
});

frappe.ui.form.on('Request for Quotation Item', {
    material_request_item: function(frm, cdt, cdn) {
        fetch_cost_center(frm, cdt, cdn);
    }
});

function fetch_cost_center(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    if (!row.material_request_item || row.custom_cost_center) return;

    frappe.call({
        method: 'oerp_custom.overrides.rfq.get_material_request_item_cost_center',
        args: { material_request_item: row.material_request_item },
    }).then((r) => {
        const mr_cost_center = r && r.message ? r.message : null;

        if (mr_cost_center) {
            frappe.model.set_value(cdt, cdn, 'custom_cost_center', mr_cost_center);
        } else {
            // fallback to company's default cost center
            apply_default_company_cost_center(frm, cdt, cdn);
        }
    }).catch((err) => {
        console.error('get_material_request_item_cost_center failed:', err);
    });
}

function apply_default_company_cost_center(frm, cdt, cdn) {
    if (!frm.doc.company) return;

    frappe.db.get_value('Company', frm.doc.company, 'cost_center')
        .then((r) => {
            const default_cc = r && r.message ? r.message.cost_center : null;
            if (default_cc) {
                frappe.model.set_value(cdt, cdn, 'custom_cost_center', default_cc);
            }
        })
        .catch((err) => {
            console.error('get_value failed (Company default cost center):', err);
        });
}

function backfill_all_cost_centers(frm) {
    (frm.doc.items || []).forEach((row) => {
        fetch_cost_center(frm, row.doctype, row.name);
    });
}