// Purchase Order form: when purchase_type is "Contract", restrict the Supplier
// link to suppliers holding a submitted Vendor Contract, and restrict the Items
// table's Item link to that supplier's contracted items. For Contract POs, the
// Rate and Amount columns are locked (read-only) so the price cannot drift off
// what the contract dictates — everything else in the table stays editable.
//
// Both restrictions are re-checked server-side in
// oerp_custom.overrides.purchase_order — this file only shapes the dropdowns
// and the grid's editability.
//
// Naming series follows the purchase type.
//
//   Service  -> PUR-SER-.YYYY.-####      Contract -> PUR-CON-.YYYY.-####
//   others   -> PUR-ORD-.YYYY.- (the standard default)
//
// The same mapping is enforced server-side in
// oerp_custom.overrides.service_naming.apply_po_naming, and a PO created from
// a service Material Request arrives with type, service type and series
// already set by the make_purchase_order override.
//
// When items are pulled in via "Get Items From" a Material Request (rather
// than mapped from a Supplier Quotation), nothing fires purchase_type
// manually — so set_service_type_from_items below detects a service Material
// Request from the row's link and sets purchase_type itself, which then
// drives naming_series through the same handler.

const PO_SERIES_BY_TYPE = {
	Service: "PUR-SER-.YYYY.-####",
	Contract: "PUR-CON-.YYYY.-####",
};
const PO_DEFAULT_SERIES = "PUR-ORD-.YYYY.-";

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		set_contract_queries(frm);
		set_items_editable(frm);
		set_service_type_from_items(frm);
	},

	items_add(frm) {
		set_service_type_from_items(frm);
	},

	purchase_type(frm) {
		// Supplier and any existing rows are no longer guaranteed to be in scope.
		if (frm.doc.supplier) {
			frm.set_value("supplier", null);
		}
		clear_items(frm);
		if (frm.doc.custom_vendor_contract) {
			frm.set_value("custom_vendor_contract", null);
		}
		set_contract_queries(frm);
		set_items_editable(frm);

		if (!frm.is_new()) {
			// The document is already numbered; the server will warn if the
			// series no longer matches. Do not fight the name here.
			return;
		}
		frm.set_value("naming_series", PO_SERIES_BY_TYPE[frm.doc.purchase_type] || PO_DEFAULT_SERIES);
		if (frm.doc.purchase_type !== "Service" && frm.doc.custom_service_type) {
			frm.set_value("custom_service_type", null);
		}
	},

	supplier(frm) {
		if (frm.doc.purchase_type === "Contract") {
			clear_items(frm);
			fetch_vendor_contract(frm);
		} else if (frm.doc.custom_vendor_contract) {
			frm.set_value("custom_vendor_contract", null);
		}
		set_contract_queries(frm);
	},
});

frappe.ui.form.on("Purchase Order Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (frm.doc.purchase_type !== "Contract" || !row.item_code || !frm.doc.supplier) {
			return;
		}

		// Pull the contracted rate so the order cannot silently drift off the
		// agreed price. ERPNext's own price-list fetch fires too, so this runs
		// after it and wins. Still relevant even with rate locked in the UI,
		// since this writes programmatically, not through manual grid entry.
		frappe.call({
			method: "oerp_custom.queries.get_contract_item_details",
			args: { vendor: frm.doc.supplier, item: row.item_code },
			callback(r) {
				if (!r.message || !r.message.rate) {
					return;
				}
				frappe.model.set_value(cdt, cdn, "rate", r.message.rate);
				if (r.message.uom) {
					frappe.model.set_value(cdt, cdn, "uom", r.message.uom);
				}
			},
		});
	},
});

function clear_items(frm) {
	if ((frm.doc.items || []).some((row) => row.item_code)) {
		frm.clear_table("items");
		frm.refresh_field("items");
	}
}

function set_items_editable(frm) {
	const is_contract = frm.doc.purchase_type === "Contract";

	// The grid itself stays fully usable — rows can still be added/removed
	// and item_code picked normally. Only Rate and Amount are locked for
	// Contract POs, since those must come from the contracted price rather
	// than manual entry.
	frm.set_df_property("items", "read_only", 0);

	if (frm.fields_dict.items && frm.fields_dict.items.grid) {
		frm.fields_dict.items.grid.update_docfield_property("rate", "read_only", is_contract ? 1 : 0);
		frm.fields_dict.items.grid.update_docfield_property("amount", "read_only", is_contract ? 1 : 0);
	}

	frm.refresh_field("items");
}

function set_contract_queries(frm) {
	if (frm.doc.purchase_type === "Contract") {
		frm.set_query("supplier", () => ({
			query: "oerp_custom.queries.contract_vendors",
		}));

		frm.set_query("custom_vendor_contract", () => ({
			query: "oerp_custom.queries.vendor_contracts",
			filters: { vendor: frm.doc.supplier },
		}));

		frm.set_query("item_code", "items", () => ({
			query: "oerp_custom.queries.contract_items",
			filters: {
				vendor: frm.doc.supplier,
				vendor_contract: frm.doc.custom_vendor_contract,
			},
		}));
	} else {
		// Restore the stock ERPNext behaviour.
		frm.set_query("supplier", erpnext.queries.supplier);
		frm.set_query("item_code", "items", () => ({
			query: "erpnext.controllers.queries.item_query",
			filters: { is_purchase_item: 1 },
		}));
	}
}

function fetch_vendor_contract(frm) {
	if (!frm.doc.supplier) {
		frm.set_value("custom_vendor_contract", null);
		return;
	}

	// Reverse of a Fetch From: the link lives on Vendor Contract pointing at the
	// supplier, not the other way round, so it has to be looked up server-side.
	frappe.call({
		method: "oerp_custom.queries.get_vendor_contract",
		args: { vendor: frm.doc.supplier },
		callback(r) {
			frm.set_value("custom_vendor_contract", r.message || null);
			if (!r.message) {
				frappe.show_alert({
					message: __("This supplier has more than one active contract — pick one."),
					indicator: "orange",
				});
			}
		},
	});
}

function set_service_type_from_items(frm) {
	// Only worth doing on a not-yet-named document — an existing PO's
	// purchase_type/series shouldn't be rewritten just because it refreshed.
	if (!frm.is_new()) {
		return;
	}

	const row = (frm.doc.items || []).find((r) => r.material_request);
	if (!row || !row.material_request) {
		return;
	}

	frappe.db
		.get_value("Material Request", row.material_request, [
			"custom_service_type",
			"custom_by_service_",
		])
		.then((r) => {
			const data = r.message || {};

			if (data.custom_service_type && !frm.doc.custom_service_type) {
				frm.set_value("custom_service_type", data.custom_service_type);
			}

			// If the source Material Request was a service request, mirror
			// that here — setting purchase_type triggers the handler above,
			// which applies the matching naming_series in one place.
			if (data.custom_by_service_ && frm.doc.purchase_type !== "Service") {
				frm.set_value("purchase_type", "Service");
			} else if (PO_SERIES_BY_TYPE[frm.doc.purchase_type]) {
				// purchase_type already matches or was independently set —
				// just make sure naming_series agrees with it.
				frm.set_value(
					"naming_series",
					PO_SERIES_BY_TYPE[frm.doc.purchase_type] || PO_DEFAULT_SERIES
				);
			}
		});
}