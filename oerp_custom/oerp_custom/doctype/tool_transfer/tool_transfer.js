frappe.ui.form.on("Tool Transfer", {
    setup: function(frm) {
        frm.set_query("reference_document_type", function() {
            return {
                filters: {
                    name: ["in", ["Purchase Receipt", "Purchase Order"]]
                }
            };
        });
    },

    onload: function(frm) {
        if (frm.is_new() && !frm.doc.purpose) {
            frm.set_value("purpose", "Tool Transfer");
        }
    }
});

// IMPORTANT: this must match your ACTUAL child table doctype name exactly
frappe.ui.form.on("Tool Transfer Child Table", {
    tool_no: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.tool_no) {
            return;
        }
        frappe.db.get_doc("Tool Registry", row.tool_no).then((doc) => {
            frappe.model.set_value(cdt, cdn, "source_location", doc.location);
            frappe.model.set_value(cdt, cdn, "from_employee", doc.custodian_employee_no);
            frappe.model.set_value(cdt, cdn, "from_crew", doc.crew_name);
            frappe.model.set_value(cdt, cdn, "asset_ref_no", doc.asset_no);
            frm.refresh_field("tools");
        });
    }
});