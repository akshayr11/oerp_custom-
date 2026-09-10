// Purchase Receipt form: naming series follows purchase_type, same pattern as
// Purchase Order. purchase_type and supplier are also pulled from the source
// Purchase Order when the Receipt is created via "Get Items From" a PO.
//
//   Service  -> PREC-SER-.YYYY.-####      Contract -> PREC-CON-.YYYY.-####
//   others   -> the standard default naming series for Purchase Receipt
//
// NOTE: Replace PR_SERIES_BY_TYPE / PR_DEFAULT_SERIES below with your actual
// series names if they differ from these placeholders. Also make sure this
// same mapping exists/is enforced server-side (mirroring
// oerp_custom.overrides.service_naming.apply_po_naming for PO) if a Purchase
// Receipt can be created or submitted through a path that bypasses this form
// script (e.g. API, bulk creation from PO).

const PR_SERIES_BY_TYPE = {
	Service: "PREC-SER-.YYYY.-",
	Contract: "PREC-CON-.YYYY.-",
};
const PR_DEFAULT_SERIES = "MAT-PRE-.YYYY.-"; // ERPNext's stock default — replace if yours differs

frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		set_pr_details_from_source(frm);
	},

	items_add(frm) {
		set_pr_details_from_source(frm);
	},

	custom_purchase_type(frm) {
		if (!frm.is_new()) {
			// The document is already numbered; the server will warn if the
			// series no longer matches. Do not fight the name here.
			return;
		}
		frm.set_value("naming_series", PR_SERIES_BY_TYPE[frm.doc.custom_purchase_type] || PR_DEFAULT_SERIES);
	},
});

function set_pr_details_from_source(frm) {
	// Only worth doing on a not-yet-named document — an existing Purchase
	// Receipt's purchase_type/series/supplier shouldn't be rewritten just
	// because it refreshed.
	if (!frm.is_new()) {
		return;
	}

	const po_row = (frm.doc.items || []).find((r) => r.purchase_order);
	const mr_row = (frm.doc.items || []).find((r) => r.material_request);

	if (po_row && po_row.purchase_order) {
		// Mapped from a Purchase Order — pull purchase_type, vendor and
		// vendor contract from it.
		frappe.db
			.get_value("Purchase Order", po_row.purchase_order, ["purchase_type", "supplier"])
			.then((r) => {
				const data = r.message || {};

				if (data.supplier && !frm.doc.supplier) {
					frm.set_value("supplier", data.supplier);
				}

				if (data.purchase_type && frm.doc.purchase_type !== data.purchase_type) {
					// Setting purchase_type triggers the handler above, which
					// applies the matching naming_series in one place.
					frm.set_value("custom_purchase_type", data.purchase_type);
				} else if (PR_SERIES_BY_TYPE[frm.doc.purchase_type]) {
					// purchase_type already matches or was independently set —
					// just make sure naming_series agrees with it.
					frm.set_value(
						"naming_series",
						PR_SERIES_BY_TYPE[frm.doc.custom_purchase_type] || PR_DEFAULT_SERIES
					);
				}
			});
	} else if (mr_row && mr_row.material_request) {
		// Mapped from a Material Request instead — fall back to the service
		// flag on the MR.
		frappe.db
			.get_value("Material Request", mr_row.material_request, ["custom_by_service_"])
			.then((r) => {
				const data = r.message || {};

				if (data.custom_by_service_ && frm.doc.purchase_type !== "Service") {
					frm.set_value("purchase_type", "Service");
				} else if (PR_SERIES_BY_TYPE[frm.doc.purchase_type]) {
					frm.set_value(
						"naming_series",
						PR_SERIES_BY_TYPE[frm.doc.purchase_type] || PR_DEFAULT_SERIES
					);
				}
			});
	}
}