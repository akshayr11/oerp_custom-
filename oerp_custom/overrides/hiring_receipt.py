# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Hiring Receipt: multiple Equipment Timesheets rolled up against one
Hiring Contract for one service month, approved by Transport, then
auto-creating a submitted Purchase Receipt against that contract's PO.

Quantity conversion (the whole point of this doctype existing separately
from the timesheet) depends on the contract item's own billing frequency:

    Daily   -> Days Worked (days with any hours logged), unchanged
    Yearly  -> Days Worked / days in that calendar year
    Hourly  -> that equipment's own Normal + Overtime hours for the period
               (days don't apply to an hourly rate at all)
    Monthly -> a different, hours-driven model (see below) — everything
               else stays the simple day-based model above.

Monthly billing model: the contract's Rate is for one full month's normal
running (e.g. 1500 for September's 300 "normal" hours = 30 days x a 10hr/day
cap from the Hiring Contract's Total Operational Hours). Normal running and
Overtime are billed at two different rates, not blended into one quantity:

    Rate        = contract Rate / that month's capacity hours (the derived
                  hourly rate, e.g. 1500 / 300 = 5)
    Quantity    = Normal + OT hours, shown for reference only (the UOM here
                  is Hourly) — it is NOT what Amount is based on
    Amount      = Normal Hours x Rate only (e.g. 285 x 5 = 1425) — Overtime
                  is deliberately excluded here
    OT Rate     = entered by the user (no OT rate on the contract to fetch)
    OT Amount   = OT Hours x OT Rate (e.g. 5 x 10 = 50)
    Deduction   = fetched from the timesheet's own Deduction Amount
    Net Amount  = Amount + OT Amount - Deduction (e.g. 1425 + 50 - 0 = 1475)
                  — this, not Amount, is what VAT is based on.

The header rolls up all four figures across rows (HiringReceipt.
calculate_totals): Total Amount, Total OT Amount, Total Deduction, Net
Amount, then Total VAT Amount and Grand Total on top of Net Amount.

At Purchase Receipt time: qty = Normal Hours / that month's capacity hours
(a month fraction, e.g. 285/300 = 0.95 — OT hours are excluded from this
conversion the same way they're excluded from Amount), rate = the
contract's original monthly Rate (e.g. 1500), uom = a real "Month" UOM
record (created on first use — see _ensure_uom). The PR's own qty x rate
therefore only ever reflects Total Amount, not Net Amount — OT Amount and
Deduction are carried across as their own custom fields on the Purchase
Receipt header instead (custom_ot_amount, custom_deduction_amount,
custom_net_amount), copied straight from this voucher's own header, rather
than folded into a line item.

VAT: a simplified version of ERPNext's own Item Tax Template resolution
(erpnext.stock.get_item_details.get_item_tax_template) — checks the item's
own Item Tax Template first, then its Item Group's, for one matching the
PO's company, and sums that template's tax rates. Doesn't walk the full
Item Group ancestor chain the core resolver does; covers the common case of
a template set directly on the item or its immediate group.
"""

import calendar

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate

DAY_FIELDS = [f"day_{d}" for d in range(1, 32)]
MONTH_NUM = {
	"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
	"July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


# ---------------------------------------------------------------------------
# Link field queries
# ---------------------------------------------------------------------------


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def timesheet_query(doctype, txt, searchfield, start, page_len, filters):
	"""Approved timesheets against this contract and service month/year,
	backing the Timesheet Link inside the Hiring Receipt grid.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	hiring_contract = filters.get("hiring_contract")
	month = filters.get("service_month")
	year = filters.get("service_year")

	if not (hiring_contract and month and year):
		return []

	return frappe.db.sql(
		"""
		select name, month
		from `tabEquipment Timesheet`
		where hiring_contract = %(hiring_contract)s
		  and docstatus = 1
		  and workflow_state = 'Approved'
		  and month(service_from_date) = %(month_num)s
		  and year(service_from_date) = %(year)s
		  and name like %(txt)s
		order by name
		limit %(start)s, %(page_len)s
		""",
		{
			"hiring_contract": hiring_contract,
			"month_num": MONTH_NUM.get(month),
			"year": year,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def equipment_in_timesheet_query(doctype, txt, searchfield, start, page_len, filters):
	"""Equipment present in the selected timesheet's own detail rows."""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	timesheet = filters.get("timesheet")
	if not timesheet:
		return []

	return frappe.db.sql(
		"""
		select distinct equipment, equipment_name
		from `tabEquipment Timesheet Detail`
		where parent = %(timesheet)s and parenttype = 'Equipment Timesheet'
		  and equipment like %(txt)s
		order by equipment
		limit %(start)s, %(page_len)s
		""",
		{"timesheet": timesheet, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


# ---------------------------------------------------------------------------
# Row detail lookup (fired when a row's Equipment is set)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_row_details(hiring_contract, timesheet, equipment):
	ts = frappe.get_doc("Equipment Timesheet", timesheet)
	ts_row = next((r for r in ts.details if r.equipment == equipment), None)
	if not ts_row:
		frappe.throw(_("{0} does not appear on timesheet {1}.").format(equipment, timesheet))

	contract_row = frappe.db.get_value(
		"Hiring Contract Item",
		{"parent": hiring_contract, "parenttype": "Hiring Contract", "equipment": equipment},
		["uom", "frequency", "rate"],
		as_dict=True,
	)
	if not contract_row:
		frappe.throw(_("{0} is not on contract {1}.").format(equipment, hiring_contract))

	billing_frequency = contract_row.frequency or "Daily"
	days_worked = sum(1 for f in DAY_FIELDS if flt(ts_row.get(f)) > 0)

	if billing_frequency == "Monthly":
		threshold = flt(frappe.db.get_value("Hiring Contract", hiring_contract, "total_operational_hours"))
		capacity_hours = _month_capacity_hours(ts.service_from_date, threshold)
		quantity = flt(ts_row.normal_hours) + flt(ts_row.overtime_hours)
		rate = flt(contract_row.rate) / capacity_hours if capacity_hours else 0
		uom = "Hour"
		amount = flt(ts_row.normal_hours) * flt(rate)
	else:
		uom = contract_row.uom
		rate = flt(contract_row.rate)
		quantity = _convert_qty(days_worked, billing_frequency, ts.service_from_date, ts_row)
		amount = flt(rate) * flt(quantity)

	# OT Rate has no contract field to fetch from — starts blank, the user
	# fills it in on the row; OT Amount/Net Amount/VAT are then kept in
	# sync by HiringReceipt.calculate_row_amounts() on every save.
	ot_rate = 0
	ot_amount = 0
	deduction_amount = flt(ts_row.deduction_amount)
	net_amount = amount + ot_amount - deduction_amount

	company = _get_company(hiring_contract)
	vat_rate = _get_item_vat_rate(equipment, company) if company else 0
	vat_amount = net_amount * vat_rate / 100 if vat_rate else 0

	return {
		"equipment_description": f"{ts_row.equipment_name or equipment} ({ts_row.vehicle_number or ''})".strip(),
		"uom": uom,
		"billing_frequency": billing_frequency,
		"rate": rate,
		"service_from": ts.service_from_date,
		"service_to": ts.service_to_date,
		"normal_hours": flt(ts_row.normal_hours),
		"overtime_hours": flt(ts_row.overtime_hours),
		"breakdown_hours": flt(ts_row.breakdown_hours),
		"days_worked": days_worked,
		"quantity": quantity,
		"amount": amount,
		"ot_rate": ot_rate,
		"ot_amount": ot_amount,
		"deduction_amount": deduction_amount,
		"net_amount": net_amount,
		"vat_rate": vat_rate,
		"vat_amount": vat_amount,
	}


def _month_capacity_hours(service_from_date, daily_threshold):
	d = getdate(service_from_date)
	days_in_month = calendar.monthrange(d.year, d.month)[1]
	return flt(daily_threshold) * days_in_month


def _convert_qty(days_worked, billing_frequency, service_from_date, ts_row):
	if billing_frequency == "Daily":
		return days_worked

	if billing_frequency == "Yearly":
		d = getdate(service_from_date)
		days_in_year = 366 if calendar.isleap(d.year) else 365
		return flt(days_worked) / days_in_year

	if billing_frequency == "Hourly":
		return flt(ts_row.normal_hours) + flt(ts_row.overtime_hours)

	return days_worked


def _get_item_vat_rate(item_code, company):
	template = frappe.db.get_value(
		"Item Tax", {"parent": item_code, "parenttype": "Item"}, "item_tax_template"
	)
	if not template:
		item_group = frappe.db.get_value("Item", item_code, "item_group")
		if item_group:
			template = frappe.db.get_value(
				"Item Tax", {"parent": item_group, "parenttype": "Item Group"}, "item_tax_template"
			)
	if not template:
		return 0

	template_company = frappe.db.get_value("Item Tax Template", template, "company")
	if template_company and template_company != company:
		return 0

	rates = frappe.get_all("Item Tax Template Detail", filters={"parent": template}, pluck="tax_rate")
	return sum(flt(r) for r in rates)


def _get_company(hiring_contract):
	fleet_hiring_request = frappe.db.get_value("Hiring Contract", hiring_contract, "fleet_hiring_request")
	if not fleet_hiring_request:
		return None
	cost_center = frappe.db.get_value("Fleet Hiring Request", fleet_hiring_request, "cost_center")
	return cost_center and frappe.db.get_value("Cost Center", cost_center, "company")


# ---------------------------------------------------------------------------
# Purchase Receipt creation (on submit)
# ---------------------------------------------------------------------------


def create_purchase_receipt(hiring_receipt_name):
	hr = frappe.get_doc("Hiring Receipt", hiring_receipt_name)

	po_name = _get_linked_purchase_order(hr.hiring_contract)
	if not po_name:
		frappe.throw(
			_("No submitted Purchase Order was found for contract {0} — cannot create a Purchase Receipt.").format(
				frappe.bold(hr.hiring_contract)
			)
		)

	po_items_by_item_code = {
		row.item_code: row.name
		for row in frappe.get_all("Purchase Order Item", filters={"parent": po_name}, fields=["item_code", "name"])
	}

	def set_missing_values(source, target):
		target.supplier_delivery_note = hr.name
		target.custom_hiring_receipt = hr.name
		target.custom_total_amount = hr.total_amount
		target.custom_ot_amount = hr.total_ot_amount
		target.custom_deduction_amount = hr.total_deduction_amount
		target.custom_net_amount = hr.net_amount
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	pr = get_mapped_doc(
		"Purchase Order",
		po_name,
		{
			"Purchase Order": {
				"doctype": "Purchase Receipt",
				"validation": {"docstatus": ["=", 1]},
			},
		},
		None,
		set_missing_values,
	)

	# Drop the PO's own (unreceived) rows — this receipt is built entirely
	# from the voucher's rows instead, so the quantities match exactly what
	# was approved on the voucher, not "whatever is still outstanding on
	# the PO". OT Amount/Deduction don't appear in these lines at all — see
	# the module docstring — they're on the header's own custom fields.
	pr.items = []

	for row in hr.timesheets:
		line = _pr_line_values(hr.hiring_contract, row)
		# A Monthly row's PR line is in "Month" units, which won't match
		# the PO item's own UOM (whatever real unit — e.g. "Nos" — the
		# contract was raised in) — ERPNext's PR-vs-PO validation enforces
		# UOM equality whenever purchase_order_item is set, so that
		# per-line reference is left out for Monthly rows. The parent
		# purchase_order link is kept either way for traceability.
		po_item_name = po_items_by_item_code.get(row.equipment) if row.billing_frequency != "Monthly" else None
		pr.append(
			"items",
			{
				"item_code": row.equipment,
				"item_name": row.equipment_description,
				"description": row.equipment_description,
				"uom": line["uom"],
				"qty": line["qty"],
				"stock_qty": line["qty"],
				"rate": line["rate"],
				"purchase_order": po_name,
				"purchase_order_item": po_item_name,
				"schedule_date": row.service_to,
			},
		)

	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr.name


def _pr_line_values(hiring_contract, row):
	"""Daily/Yearly/Hourly rows carry their voucher Quantity/Rate across
	unchanged. A Monthly row's voucher values are in hours (see the module
	docstring), so this converts them back to the contract's actual
	monthly rate and a Normal-Hours-only month-fraction quantity — OT
	Amount/Deduction never appear here, they're on the Purchase Receipt's
	own header fields instead (see create_purchase_receipt).
	"""
	if row.billing_frequency != "Monthly":
		return {"uom": row.uom, "qty": flt(row.quantity), "rate": flt(row.rate)}

	contract_rate = frappe.db.get_value(
		"Hiring Contract Item",
		{"parent": hiring_contract, "parenttype": "Hiring Contract", "equipment": row.equipment},
		"rate",
	)
	threshold = flt(frappe.db.get_value("Hiring Contract", hiring_contract, "total_operational_hours"))
	capacity_hours = _month_capacity_hours(row.service_from, threshold)
	qty = flt(row.normal_hours) / capacity_hours if capacity_hours else flt(row.normal_hours)

	uom = _ensure_uom("Month")
	_ensure_fraction_friendly_stock_uom(row.equipment, uom)

	return {"uom": uom, "qty": qty, "rate": flt(contract_rate)}


def _ensure_uom(uom_name):
	if not frappe.db.exists("UOM", uom_name):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom_name, "must_be_whole_number": 0}).insert(
			ignore_permissions=True
		)
	return uom_name


def _ensure_fraction_friendly_stock_uom(item_code, uom_name):
	"""A Monthly row's PR quantity is a month fraction (e.g. 0.95) — if the
	item's own Stock UOM enforces whole numbers (ERPNext's "Nos" default
	does), receipting a fraction against it fails validation regardless of
	the transaction UOM used. Only safe to repoint at this item's own Stock
	UOM when it has no stock ledger history yet (true for any equipment
	that hasn't been through a stock-tracked movement, which is the normal
	case for hired-out, non-stock equipment) — otherwise this would risk
	corrupting existing valuation, so it throws instead of guessing.
	"""
	current_stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if current_stock_uom == uom_name:
		return
	if not frappe.db.get_value("UOM", current_stock_uom, "must_be_whole_number"):
		return
	if frappe.db.exists("Stock Ledger Entry", {"item_code": item_code}):
		frappe.throw(
			_(
				"{0}'s Stock UOM is {1}, which only allows whole numbers — Monthly billing needs "
				"fractional quantities. Change its Stock UOM to a fraction-friendly unit (e.g. {2}) "
				"manually; this couldn't be done automatically because the item already has stock "
				"ledger history."
			).format(frappe.bold(item_code), frappe.bold(current_stock_uom), frappe.bold(uom_name))
		)
	frappe.db.set_value("Item", item_code, "stock_uom", uom_name)

	# A raw db.set_value bypasses Item's own controller, which is what
	# normally keeps the UOM Conversion Detail child table (its "UOMs"
	# grid) in sync with Stock UOM — ERPNext's own item-detail/price
	# lookups expect the transaction UOM to appear there, so it's added
	# directly here too (conversion factor 1: it's now the stock UOM).
	if not frappe.db.exists("UOM Conversion Detail", {"parenttype": "Item", "parent": item_code, "uom": uom_name}):
		frappe.get_doc(
			{
				"doctype": "UOM Conversion Detail",
				"parent": item_code,
				"parenttype": "Item",
				"parentfield": "uoms",
				"uom": uom_name,
				"conversion_factor": 1,
			}
		).insert(ignore_permissions=True)


def _get_linked_purchase_order(hiring_contract):
	fleet_hiring_request = frappe.db.get_value("Hiring Contract", hiring_contract, "fleet_hiring_request")
	if not fleet_hiring_request:
		return None
	return frappe.db.get_value(
		"Purchase Order",
		{"custom_reference_hiring_request": fleet_hiring_request, "docstatus": 1},
		"name",
	)
