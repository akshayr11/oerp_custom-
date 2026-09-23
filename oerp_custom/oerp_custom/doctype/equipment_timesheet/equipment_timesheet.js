// Copyright (c) 2026, akshay and contributors
// For license information, please see license.txt

const DAY_FIELDS = Array.from({ length: 31 }, (_, i) => `day_${i + 1}`);

frappe.ui.form.on("Equipment Timesheet", {
	setup(frm) {
		// Only a live (submitted, not cancelled) contract has real equipment
		// rows and a Total Operational Hours cap to compute against.
		frm.set_query("hiring_contract", () => {
			return { filters: { docstatus: 1 } };
		});
	},

	refresh(frm) {
		if (frm.doc.hiring_contract && frm.is_new()) {
			frm.add_custom_button(__("Equipment from Contract"), () => get_equipment_from_contract(frm), __("Get"));
		}

		if ((frm.doc.details || []).length) {
			frm.add_custom_button(__("Apply Same Hours to All"), () => apply_same_hours_dialog(frm));
		}

		if (frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(__("Hiring Receipt"), () => {
				frappe.model.open_mapped_doc({
					method: "oerp_custom.overrides.equipment_timesheet.create_hiring_receipt",
					frm: frm,
				});
			}, __("Create"));
		}
	},

	hiring_contract(frm) {
		frm._contract_threshold = undefined;
		frm._monthly_equipment_set = undefined;
		frm.refresh();
	},
});

const NOT_BILLABLE_STATUSES = new Set(["Idle", "Overtime", "Off", "De-hired"]);

frappe.ui.form.on("Equipment Timesheet Detail", {
	equipment(frm, cdt, cdn) {
		recalculate_row(frm, cdt, cdn);
	},
	status(frm, cdt, cdn) {
		recalculate_row(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		update_net_rate(frm, cdt, cdn);
	},
	deduction_amount(frm, cdt, cdn) {
		update_net_rate(frm, cdt, cdn);
	},
	extra_charges(frm, cdt, cdn) {
		update_net_rate(frm, cdt, cdn);
	},
	ot_amount(frm) {
		update_totals(frm);
	},
});

// One handler shared by all 31 day fields, wired below.
DAY_FIELDS.forEach((fieldname) => {
	frappe.ui.form.on("Equipment Timesheet Detail", fieldname, (frm, cdt, cdn) => {
		recalculate_row(frm, cdt, cdn);
	});
});

function get_equipment_from_contract(frm) {
	frappe.call({
		method: "frappe.client.get",
		args: { doctype: "Hiring Contract", name: frm.doc.hiring_contract },
		callback(r) {
			const contract = r.message;
			if (!contract || !contract.items || !contract.items.length) {
				frappe.msgprint(__("This contract has no equipment rows."));
				return;
			}

			frm.clear_table("details");
			contract.items.forEach((item) => {
				const row = frm.add_child("details", {
					equipment: item.equipment,
					equipment_name: item.equipment_name,
					vehicle_number: item.vehicle_number,
					rate: item.rate,
				});
			});
			frm.refresh_field("details");
		},
	});
}

function apply_same_hours_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Apply Same Hours to All"),
		fields: [
			{
				fieldname: "hours",
				fieldtype: "Float",
				label: __("Hours per Day"),
				reqd: 1,
			},
			{
				fieldname: "from_day",
				fieldtype: "Int",
				label: __("From Day"),
				default: 1,
				reqd: 1,
			},
			{
				fieldname: "to_day",
				fieldtype: "Int",
				label: __("To Day"),
				default: 31,
				reqd: 1,
			},
		],
		primary_action_label: __("Apply"),
		primary_action(values) {
			const from_day = Math.max(1, cint(values.from_day));
			const to_day = Math.min(31, cint(values.to_day));

			(frm.doc.details || []).forEach((row) => {
				for (let day = from_day; day <= to_day; day++) {
					frappe.model.set_value(row.doctype, row.name, `day_${day}`, values.hours);
				}
			});
			d.hide();
		},
	});
	d.show();
}

function recalculate_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	const active_day_fields = get_active_day_fields(frm);

	const apply = (contract_threshold, monthly_equipment) => {
		let day_total = 0;
		active_day_fields.forEach((f) => (day_total += flt(row[f])));

		if (NOT_BILLABLE_STATUSES.has(row.status)) {
			// Idle / Overtime / Off / De-hired: not ordinary running time,
			// so nothing here is billable regardless of hours entered.
			row.normal_hours = 0;
			row.overtime_hours = 0;
			row.breakdown_hours = 0;
		} else if (row.status === "Breakdown") {
			row.breakdown_hours = day_total;
			row.normal_hours = 0;
			row.overtime_hours = 0;
		} else if (contract_threshold) {
			let normal = 0;
			let overtime = 0;
			let deficit = 0;
			active_day_fields.forEach((f) => {
				const value = flt(row[f]);
				normal += Math.min(value, contract_threshold);
				overtime += Math.max(0, value - contract_threshold);
				deficit += Math.max(0, contract_threshold - value);
			});
			row.normal_hours = normal;
			row.overtime_hours = overtime;
			// Breakdown as a deficit-from-threshold only applies to
			// Monthly-billed contract items — everything else keeps 0,
			// same as before.
			row.breakdown_hours = monthly_equipment.has(row.equipment) ? deficit : 0;
		} else {
			row.normal_hours = day_total;
			row.overtime_hours = 0;
			row.breakdown_hours = 0;
		}

		// Deduction Amount, Extra Charges and OT Amount are the user's own
		// entries, not derived from hours — only Net Rate is computed from
		// them.
		row.net_rate = flt(row.rate) - flt(row.deduction_amount) + flt(row.extra_charges);

		frm.refresh_field("details");
		update_totals(frm);
	};

	Promise.all([get_contract_threshold(frm), get_monthly_equipment_set(frm)]).then(
		([threshold, monthly_equipment]) => apply(threshold, monthly_equipment)
	);
}

function get_active_day_fields(frm) {
	// Bound to the timesheet's own period length — a 30-day period's
	// day_31 field isn't a real day, and must not be treated as "0 hours
	// logged, so a full threshold's worth of breakdown deficit."
	if (!(frm.doc.service_from_date && frm.doc.service_to_date)) {
		return DAY_FIELDS;
	}
	const from = frappe.datetime.str_to_obj(frm.doc.service_from_date);
	const to = frappe.datetime.str_to_obj(frm.doc.service_to_date);
	let period_days = Math.round((to - from) / (1000 * 60 * 60 * 24)) + 1;
	period_days = Math.max(1, Math.min(31, period_days));
	return DAY_FIELDS.slice(0, period_days);
}

function get_contract_threshold(frm) {
	if (frm._contract_threshold !== undefined) {
		return Promise.resolve(frm._contract_threshold);
	}
	return frappe.db
		.get_value("Hiring Contract", frm.doc.hiring_contract, "total_operational_hours")
		.then((r) => {
			frm._contract_threshold = flt(r.message && r.message.total_operational_hours);
			return frm._contract_threshold;
		});
}

function get_monthly_equipment_set(frm) {
	if (frm._monthly_equipment_set !== undefined) {
		return Promise.resolve(frm._monthly_equipment_set);
	}
	return frappe
		.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Hiring Contract Item",
				filters: {
					parent: frm.doc.hiring_contract,
					parenttype: "Hiring Contract",
					frequency: "Monthly",
				},
				fields: ["equipment"],
				limit_page_length: 0,
			},
		})
		.then((r) => {
			frm._monthly_equipment_set = new Set((r.message || []).map((d) => d.equipment));
			return frm._monthly_equipment_set;
		});
}

function update_net_rate(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	row.net_rate = flt(row.rate) - flt(row.deduction_amount) + flt(row.extra_charges);
	frm.refresh_field("details");
	update_totals(frm);
}

function update_totals(frm) {
	const totals = (frm.doc.details || []).reduce(
		(acc, row) => {
			acc.normal += flt(row.normal_hours);
			acc.ot += flt(row.overtime_hours);
			acc.bd += flt(row.breakdown_hours);
			acc.deduction += flt(row.deduction_amount);
			acc.extra += flt(row.extra_charges);
			acc.ot_amount += flt(row.ot_amount);
			return acc;
		},
		{ normal: 0, ot: 0, bd: 0, deduction: 0, extra: 0, ot_amount: 0 }
	);

	frm.set_value("total_normal_hours", totals.normal);
	frm.set_value("total_overtime_hours", totals.ot);
	frm.set_value("total_breakdown_hours", totals.bd);
	frm.set_value("total_deduction", totals.deduction);
	frm.set_value("total_extra_charges", totals.extra);
	frm.set_value("total_ot_amount", totals.ot_amount);
}
