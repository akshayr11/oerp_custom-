// Item: Item Group (labelled "Item Sub Category" on the form) mirrors the
// selected Service Type value directly, and Item Main Category (fieldname
// item_sub_category — named the opposite of its own label) is set to that
// Item Group's own parent in the Item Group tree.
// oerp_custom.overrides.item.sync_item_group_from_service_type re-applies
// this on validate, so API/import-created Items follow the same rule.
//
// Note: item_group is a Link to Item Group, so this only sticks if an Item
// Group named exactly the same as the Service Type already exists.

frappe.ui.form.on("Item", {
	custom_service_type(frm) {
		if (!frm.doc.custom_service_type) {
			return;
		}

		frm.set_value("item_group", frm.doc.custom_service_type).then(() => {
			frappe.db
				.get_value("Item Group", frm.doc.item_group, "parent_item_group")
				.then((r) => {
					const parent_item_group = r.message && r.message.parent_item_group;
					if (parent_item_group) {
						frm.set_value("item_sub_category", parent_item_group);
					}
				});
		});
	},
});
