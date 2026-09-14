// Client Script
// Doctype: Supplier Quotation
// Setup:
// 1. Go to Client Script (list view) -> New
// 2. Doctype: Supplier Quotation
// 3. Enabled: checked
// 4. Paste the code below into the "Script" field
// 5. Save
//
// Requires oerp_custom/oerp_custom/queries.py to have
// get_rfq_item_cost_center (@frappe.whitelist()).
//
// Cost Center backfill uses a server call (not frappe.db.get_value) because
// Request for Quotation Item is a child table with no independent Role
// Permission entries — the client-side get_value endpoint silently strips
// custom fields like custom_cost_center for non-Administrator roles.

frappe.ui.form.on('Supplier Quotation', {
    refresh: function(frm) {
        backfill_all_cost_centers(frm);
    },

    items_add: function(frm, cdt, cdn) {
        fetch_rfq_cost_center(frm, cdt, cdn);
    },
});

frappe.ui.form.on('Supplier Quotation Item', {
    request_for_quotation_item: function(frm, cdt, cdn) {
        fetch_rfq_cost_center(frm, cdt, cdn);
    }
});

function fetch_rfq_cost_center(frm, cdt, cdn) {
    const row = locals[cdt][cdn];

    if (!row.request_for_quotation_item || row.cost_center) return;

    frappe.call({
        method: 'oerp_custom.queries.get_rfq_item_cost_center',
        args: { request_for_quotation_item: row.request_for_quotation_item },
    }).then((r) => {
        const rfq_cost_center = r && r.message ? r.message : null;

        if (rfq_cost_center) {
            frappe.model.set_value(cdt, cdn, 'cost_center', rfq_cost_center);
        }
    }).catch((err) => {
        console.error('get_rfq_item_cost_center failed:', err);
    });
}

function backfill_all_cost_centers(frm) {
    (frm.doc.items || []).forEach((row) => {
        fetch_rfq_cost_center(frm, row.doctype, row.name);
    });
}