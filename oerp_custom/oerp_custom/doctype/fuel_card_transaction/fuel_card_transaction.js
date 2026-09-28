// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fuel Card Transaction", {
	setup(frm) {
		frm.set_query("fuel_card", () => {
			return { filters: { status: "Active" } };
		});

		frm.set_query("equipment", () => {
			return {
				query: "oerp_custom.overrides.fuel_card_transaction.equipment_query",
				filters: { fuel_card: frm.doc.fuel_card },
			};
		});
	},

	fuel_card(frm) {
		frm.set_value("equipment", null);
		frm.set_df_property("equipment", "read_only", 0);

		if (!frm.doc.fuel_card) {
			return;
		}
		frappe.call({
			method: "oerp_custom.overrides.fuel_card_transaction.get_card_equipment",
			args: { fuel_card: frm.doc.fuel_card },
			callback(r) {
				const linked = r.message || [];
				if (linked.length === 1) {
					frm.set_value("equipment", linked[0]);
					frm.set_df_property("equipment", "read_only", 1);
				}
				update_preview(frm);
			},
		});
	},

	transaction_date(frm) {
		update_preview(frm);
	},

	quantity(frm) {
		update_preview(frm);
	},
});

function update_preview(frm) {
	if (!(frm.doc.fuel_card && frm.doc.transaction_date)) {
		return;
	}

	frappe.call({
		method: "oerp_custom.overrides.fuel_card_transaction.get_fuel_price_for_card",
		args: { fuel_card: frm.doc.fuel_card, transaction_date: frm.doc.transaction_date },
		callback(r) {
			if (r.message !== undefined) {
				frm.set_value("fuel_price", r.message);
			}
		},
	});

	frappe.call({
		method: "oerp_custom.overrides.fuel_card_transaction.get_balance_preview",
		args: {
			fuel_card: frm.doc.fuel_card,
			transaction_date: frm.doc.transaction_date,
			quantity: frm.doc.quantity || 0,
			exclude_name: frm.doc.name,
		},
		callback(r) {
			if (r.message !== undefined) {
				frm.set_value("balance_quantity", r.message);
			}
		},
	});
}
