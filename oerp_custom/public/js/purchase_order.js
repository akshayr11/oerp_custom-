// Purchase Order form: when purchase_type is "Contract", restrict the Supplier
// link to suppliers holding a submitted Vendor Contract, and restrict the Items
// table's Item link to that supplier's contracted items.
//
// Both restrictions are re-checked server-side in
// oerp_custom.overrides.purchase_order — this file only shapes the dropdowns.

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		set_contract_queries(frm);
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
		// after it and wins.
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


// ---------------------------------------------------------------------------
// Naming series follows the purchase type.
//
//   Service  -> PUR-SER-.YYYY.-####      Contract -> PUR-CON-.YYYY.-####
//   others   -> PUR-ORD-.YYYY.- (the standard default)
//
// The same mapping is enforced server-side in
// oerp_custom.overrides.service_naming.apply_po_naming, and a PO created from
// a service Material Request arrives with type, service type and series
// already set by the make_purchase_order override.
// ---------------------------------------------------------------------------

const PO_SERIES_BY_TYPE = {
	Service: "PUR-SER-.YYYY.-####",
	Contract: "PUR-CON-.YYYY.-####",
};
const PO_DEFAULT_SERIES = "PUR-ORD-.YYYY.-";

frappe.ui.form.on("Purchase Order", {
	purchase_type(frm) {
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
});
