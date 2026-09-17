// Item: Item Group mirrors the selected Service Type's own category
// (Service Type.service_category, itself a link to Item Group).
// oerp_custom.overrides.item.sync_item_group_from_service_type re-applies
// this on validate, so API/import-created Items follow the same rule.

frappe.ui.form.on("Item", {
	custom_service_type(frm) {
		if (!frm.doc.custom_service_type) {
			return;
		}

		frappe.db
			.get_value("Service Type", frm.doc.custom_service_type, "service_category")
			.then((r) => {
				const service_category = r.message && r.message.service_category;
				if (service_category) {
					frm.set_value("item_group", service_category);
				}
			});
	},
});
