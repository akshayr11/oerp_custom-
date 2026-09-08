frappe.ui.form.on("Tools Disposal", {
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.disposal_date) {
            frm.set_value("disposal_date", frappe.datetime.get_today());
        }
    }
});

frappe.ui.form.on("Tools Disposal Item", {
    tool_no: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.tool_no) {
            return;
        }
        frappe.db.get_doc("Tool Registry", row.tool_no).then((doc) => {
            frappe.model.set_value(cdt, cdn, "item_code", doc.item_code);
            frappe.model.set_value(cdt, cdn, "location", doc.location);
            frappe.model.set_value(cdt, cdn, "custodian_employee_no", doc.custodian_employee_no);
            frappe.model.set_value(cdt, cdn, "crew_name", doc.crew_name);
            frappe.model.set_value(cdt, cdn, "asset_no", doc.asset_no);
            frm.refresh_field("tools");
        });
    }
});