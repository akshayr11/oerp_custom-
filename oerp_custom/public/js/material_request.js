// Material Request: the "By Service" checkbox.
//
// Ticked:   series SER-MR-.YYYY.-####, Service Type mandatory (via
//           mandatory_depends_on on the field), and the Item dropdown offers
//           only service items (Maintain Stock off) that match the same
//           Service Type selected on this Material Request.
// Unticked: back to the standard series; the item dropdown is unrestricted.
//
// Everything here is convenience — oerp_custom.overrides.service_naming
// re-checks it all on validate, so API-created documents follow the same rules.

const MR_SERVICE_SERIES = "SER-MR-.YYYY.-####";
const MR_DEFAULT_SERIES = "MAT-MR-.YYYY.-";

frappe.ui.form.on("Material Request", {
	setup(frm) {
		set_service_item_query(frm);
	},

	refresh(frm) {
		set_service_item_query(frm);
	},

	custom_by_service_(frm) {
		if (frm.doc.custom_by_service_) {
			frm.set_value("naming_series", MR_SERVICE_SERIES);

			// Rows picked before the tick may be stock items — they would be
			// refused at save, so point them out now.
			const stock_rows = (frm.doc.items || []).filter((r) => r.item_code);
			if (stock_rows.length) {
				frappe.msgprint({
					title: __("Check the item rows"),
					indicator: "orange",
					message: __(
						"This is now a service request: only service items (Maintain Stock off) matching the selected Service Type are allowed. Rows already entered will be checked when you save."
					),
				});
			}
		} else {
			frm.set_value("naming_series", MR_DEFAULT_SERIES);
			if (frm.doc.custom_service_type) {
				frm.set_value("custom_service_type", null);
			}
		}
		set_service_item_query(frm);
	},

	// Re-filter the moment the Service Type changes, so the dropdown always
	// reflects the currently selected type (not just at load/refresh).
	custom_service_type(frm) {
		set_service_item_query(frm);
	},
});

function set_service_item_query(frm) {
	frm.set_query("item_code", "items", () => {
		const filters = { disabled: 0 };
		if (frm.doc.custom_by_service_) {
			// Service items are the ones that do not maintain stock.
			filters.is_stock_item = 0;

			// Further narrow to items tagged with the same Service Type as
			// this request, if one has been chosen yet.
			if (frm.doc.custom_service_type) {
				filters.custom_service_type = frm.doc.custom_service_type;
			}
		}
		return { filters };
	});
}

// --- Per-warehouse Min/Max Qty lookup ---
//
// min_qty / max_qty on Material Request Item come from the item's
// "Re-order Levels" child table (Item Reorder), matched by the row's
// warehouse, and refresh whenever the item or warehouse changes.
frappe.ui.form.on("Material Request Item", {
	item_code(frm, cdt, cdn) {
		update_qty_levels(frm, cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		update_qty_levels(frm, cdt, cdn);
	},
});

function update_qty_levels(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item_code || !row.warehouse) {
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Item Reorder",
			parent: "Item", // parent DocType — required for child-table reads
			filters: {
				parent: row.item_code, // the Item name
				parenttype: "Item",
				warehouse: row.warehouse,
			},
			fields: ["warehouse_reorder_level", "warehouse_reorder_qty"],
			limit_page_length: 1,
		},
		callback(r) {
			// The row may have moved on while the call was in flight.
			const current = locals[cdt][cdn];
			if (!current || current.item_code !== row.item_code || current.warehouse !== row.warehouse) {
				return;
			}

			const level = r.message && r.message.length ? r.message[0] : null;
			frappe.model.set_value(cdt, cdn, "min_qty", level ? level.warehouse_reorder_level : null);
			frappe.model.set_value(cdt, cdn, "max_qty", level ? level.warehouse_reorder_qty : null);
		},
	});
}