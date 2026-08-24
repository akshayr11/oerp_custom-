// Material Request: the "By Service" checkbox.
//
// Ticked:   series SER-MR-.YYYY.-####, Service Type mandatory (via
//           mandatory_depends_on on the field), and the Item dropdown offers
//           only service items (Maintain Stock off).
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
						"This is now a service request: only service items (Maintain Stock off) are allowed. Rows already entered will be checked when you save."
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
});

function set_service_item_query(frm) {
	frm.set_query("item_code", "items", () => {
		const filters = { disabled: 0 };
		if (frm.doc.custom_by_service_) {
			// Service items are the ones that do not maintain stock.
			filters.is_stock_item = 0;
		}
		return { filters };
	});
}
