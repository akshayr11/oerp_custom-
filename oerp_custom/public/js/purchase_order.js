// Purchase Order form.
//
// Vendor Contract on item rows
// ----------------------------
// Each Purchase Order Item row carries its own Vendor Contract link. Its
// dropdown is narrowed twice: to the header's supplier, and to contracts that
// actually list that row's item. When exactly one contract covers the item it
// is filled in automatically; when several do, the row is left blank and the
// (already filtered) dropdown is the pick list.
//
// This is not tied to purchase_type — it applies to every Purchase Order.
// Both conditions are re-checked server-side in
// oerp_custom.overrides.purchase_order, since the API and Data Import never
// touch this file.
//
// Naming series
// -------------
// Service POs use PUR-SER-.YYYY.-####; everything else keeps the standard
// PUR-ORD-.YYYY.- default. The same mapping is enforced server-side in
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
};
const PO_DEFAULT_SERIES = "PUR-ORD-.YYYY.-";

frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		set_contract_query(frm);
		set_service_type_from_items(frm);
	},

	items_add(frm) {
		set_service_type_from_items(frm);
	},

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

	supplier(frm) {
		// Every row's contract belonged to the previous supplier.
		refresh_row_contracts(frm);
	},
});

frappe.ui.form.on("Purchase Order Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		// The contract already on the row was resolved for the previous item
		// and may not cover the new one — drop it before re-resolving.
		if (row.custom_vendor_contract) {
			frappe.model.set_value(cdt, cdn, "custom_vendor_contract", null);
		}

		resolve_row_contract(frm, cdt, cdn);
	},
});

function resolve_row_contract(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row || !row.item_code || !frm.doc.supplier) {
		return;
	}

	frappe.call({
		method: "oerp_custom.queries.get_contract_item_details",
		args: { vendor: frm.doc.supplier, item: row.item_code },
		callback(r) {
			const data = r.message || {};

			if (data.contract) {
				frappe.model.set_value(cdt, cdn, "custom_vendor_contract", data.contract);
			} else if (data.contract_count > 1) {
				// Left blank on purpose — the dropdown on this row is already
				// filtered down to these, so the pick is a short one.
				frappe.show_alert({
					message: __("Row {0}: {1} contracts cover {2} — pick one.", [
						row.idx,
						data.contract_count,
						row.item_code,
					]),
					indicator: "orange",
				});
			}
			// contract_count === 0 is ordinary: the item is simply not under
			// contract with this supplier, and the row stays blank in silence.
		},
	});
}

function refresh_row_contracts(frm) {
	(frm.doc.items || []).forEach((row) => {
		if (row.custom_vendor_contract) {
			frappe.model.set_value(row.doctype, row.name, "custom_vendor_contract", null);
		}
		resolve_row_contract(frm, row.doctype, row.name);
	});
}

function set_contract_query(frm) {
	// This supplier's live contracts that list this row's item.
	frm.set_query("custom_vendor_contract", "items", (doc, cdt, cdn) => {
		const row = locals[cdt][cdn] || {};
		return {
			query: "oerp_custom.queries.vendor_contracts",
			filters: {
				vendor: doc.supplier,
				item: row.item_code,
			},
		};
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
