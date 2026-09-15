// Material Request: the "By Service" checkbox.
//
// Ticked:   series SER-MR-.YYYY.-, Service Type mandatory (via
//           mandatory_depends_on on the field), and the Item dropdown offers
//           only service items (Maintain Stock off) that match the same
//           Service Type selected on this Material Request.
// Unticked: back to the standard series; the item dropdown only offers
//           stock items (Maintain Stock on).
//
// Required By (schedule_date) auto-sets based on Priority, but only for
// new/unsaved documents or when the user actively changes Priority — never
// on a plain refresh of an already-saved document, since that would mark it
// dirty (and block actions like "Create > Request for Quotation") just from
// opening it.
//      - Priority = "Default" -> Required By = Today + 7 days
//      - Priority = "Urgent"  -> Required By = Today + 3 days
//
// Everything here is convenience — oerp_custom.overrides.service_naming
// re-checks it all on validate, so API-created documents follow the same rules.
//
// NOTE: MR_SERVICE_SERIES below must stay byte-for-byte identical to
// MR_SERVICE_SERIES in service_naming.py. The server overwrites naming_series
// in before_insert regardless of what the client set, so a mismatch here
// won't corrupt saved data — but it will show the wrong value in the Naming
// Series field for the moment before save, and may not match a registered
// series option.

const MR_SERVICE_SERIES = "SER-MR-.YYYY.-";
const MR_DEFAULT_SERIES = "MAT-MR-.YYYY.-";

frappe.ui.form.on("Material Request", {
	setup(frm) {
		set_item_filter(frm);
	},

	refresh(frm) {
		set_item_filter(frm);

		// Only auto-populate Required By for brand-new documents. Opening an
		// already-saved MR should never silently dirty the form.
		if (frm.is_new()) {
			set_required_by(frm);
		}

		// Rows added via "Get Items From" (BOM / Sales Order) are inserted
		// with frappe.model.add_child + direct property assignment, which
		// never fires the "item_code" row trigger below — so those rows
		// would otherwise never get a Last Purchase UOM. Backfill any row
		// that has an item but no UOM yet, same as fetch_from self-heals.
		(frm.doc.items || []).forEach((row) => {
			if (row.item_code && !row.custom_last_purchase_uom) {
				update_last_purchase_uom(frm, row.doctype, row.name);
			}
		});
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
		set_item_filter(frm);
	},

	// Re-filter the moment the Service Type changes, so the dropdown always
	// reflects the currently selected type (not just at load/refresh).
	custom_service_type(frm) {
		set_item_filter(frm);
	},

	priority(frm) {
		// User explicitly changed Priority — fine to recompute here, this is
		// a deliberate edit, not a page load.
		set_required_by(frm);
	},
});

function set_item_filter(frm) {
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
		} else {
			// Standard (non-service) request — stock items only.
			filters.is_stock_item = 1;
		}

		return { filters };
	});
}

function set_required_by(frm) {
	let days = null;

	if (frm.doc.priority === "Urgent") {
		days = 3;
	} else if (frm.doc.priority === "Default") {
		days = 7;
	}

	if (days === null) {
		return;
	}

	let new_date = frappe.datetime.add_days(frappe.datetime.get_today(), days);

	// Set header-level Required By (schedule_date)
	frm.set_value("schedule_date", new_date);

	// Also update Required By on every item row
	(frm.doc.items || []).forEach(function (row) {
		frappe.model.set_value(row.doctype, row.name, "schedule_date", new_date);
	});
}

// --- Per-warehouse Min/Max Qty lookup, and Last Purchase UOM ---
//
// min_qty / max_qty on Material Request Item come from the item's
// "Re-order Levels" child table (Item Reorder), matched by the row's
// warehouse, and refresh whenever the item or warehouse changes.
//
// custom_last_purchase_uom mirrors core's own last_purchase_price behavior:
// it looks up the UOM used on the item's most recent submitted Purchase
// Invoice (falling back to Purchase Receipt if the item was only ever
// received, never separately invoiced), so buyers can see at a glance what
// unit it's normally bought in.
frappe.ui.form.on("Material Request Item", {
	item_code(frm, cdt, cdn) {
		if (!locals[cdt][cdn].item_code) {
			// Item was cleared on this row — clear the derived fields too,
			// rather than leaving stale values from the previous item_code.
			frappe.model.set_value(cdt, cdn, "min_qty", null);
			frappe.model.set_value(cdt, cdn, "max_qty", null);
			frappe.model.set_value(cdt, cdn, "custom_last_purchase_uom", null);
			return;
		}
		update_qty_levels(frm, cdt, cdn);
		update_last_purchase_uom(frm, cdt, cdn);
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

function update_last_purchase_uom(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	if (!row.item_code) {
		frappe.model.set_value(cdt, cdn, "custom_last_purchase_uom", null);
		return;
	}

	const item_code = row.item_code;

	frappe.call({
		method: "oerp_custom.overrides.service_naming.get_last_purchase_uom",
		args: {
			item_code: item_code
		},
		callback(r) {
			const current = locals[cdt][cdn];

			if (!current || current.item_code !== item_code) {
				return;
			}

			frappe.model.set_value(
				cdt,
				cdn,
				"custom_last_purchase_uom",
				r.message || null
			);
		},
		error(r) {
			console.error("Failed to get last purchase UOM:", r);
		}
	});
}
