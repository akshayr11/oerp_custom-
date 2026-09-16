const PR_SERIES_BY_TYPE = {
	Service: "PREC-SER-.YYYY.-",
	Contract: "PREC-CON-.YYYY.-",
};
const PR_DEFAULT_SERIES = "MAT-PRE-.YYYY.-"; // ERPNext's stock default — replace if yours differs

frappe.ui.form.on("Purchase Receipt", {
	onload(frm) {
		// Default actual_consumption_year to the current year on a new document only.
		if (frm.is_new() && !frm.doc.actual_consumption_year) {
			frm.set_value("actual_consumption_year", new Date().getFullYear());
		}
	},

	refresh(frm) {
		set_pr_details_from_source(frm);
	},

	items_add(frm) {
		set_pr_details_from_source(frm);
	},

	custom_purchase_type(frm) {
		if (!frm.is_new()) {
			return;
		}
		frm.set_value("naming_series", PR_SERIES_BY_TYPE[frm.doc.custom_purchase_type] || PR_DEFAULT_SERIES);
	},
});

function set_pr_details_from_source(frm) {
	if (!frm.is_new()) {
		return;
	}

	const po_row = (frm.doc.items || []).find((r) => r.purchase_order);
	const mr_row = (frm.doc.items || []).find((r) => r.material_request);

	if (po_row && po_row.purchase_order) {
		frappe.db
			.get_value("Purchase Order", po_row.purchase_order, [
				"purchase_type",
				"supplier",
				"custom_service_type",
			])
			.then((r) => {
				const data = r.message || {};

				if (data.supplier && !frm.doc.supplier) {
					frm.set_value("supplier", data.supplier);
				}

				if (data.custom_service_type && !frm.doc.custom_service_type) {
					frm.set_value("custom_service_type", data.custom_service_type);
				}

				if (data.purchase_type && frm.doc.purchase_type !== data.purchase_type) {
					frm.set_value("custom_purchase_type", data.purchase_type);
				} else if (PR_SERIES_BY_TYPE[frm.doc.purchase_type]) {
					frm.set_value(
						"naming_series",
						PR_SERIES_BY_TYPE[frm.doc.custom_purchase_type] || PR_DEFAULT_SERIES
					);
				}
			});
	} else if (mr_row && mr_row.material_request) {
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