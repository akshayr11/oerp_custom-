// Item: Item Group mirrors the selected Service Type value directly.
// oerp_custom.overrides.item.sync_item_group_from_service_type re-applies
// this on validate, so API/import-created Items follow the same rule.
//
// Note: item_group is a Link to Item Group, so this only sticks if an Item
// Group named exactly the same as the Service Type already exists.

frappe.ui.form.on("Item", {
	custom_service_type(frm) {
		if (frm.doc.custom_service_type) {
			frm.set_value("item_group", frm.doc.custom_service_type);
		}
	},
});
