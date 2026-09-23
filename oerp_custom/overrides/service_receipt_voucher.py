# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Service Receipt Voucher: multiple Equipment Timesheets rolled up against
one Hiring Contract for one service month, approved by Transport, then
auto-creating a submitted Purchase Receipt against that contract's PO.

Quantity conversion (the whole point of this doctype existing separately
from the timesheet): each row's Days Worked (how many days that equipment
has non-zero hours logged, within its timesheet) is converted to the
contract's own UOM before anything downstream sees it — a Monthly contract
never sees "31", it sees "1":

    Daily   -> Days Worked, unchanged
    Monthly -> Days Worked / days in that calendar month
    Yearly  -> Days Worked / days in that calendar year
    Hourly  -> that equipment's own Normal + Overtime hours for the period
               (days don't apply to an hourly rate at all)

That converted number is stored as this row's own Quantity — the Purchase
Receipt just copies it across unchanged, no second conversion at PR time.

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
	backing the Timesheet Link inside the Service Receipt Voucher grid.
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

	uom = contract_row.uom
	billing_frequency = contract_row.frequency or "Daily"
	rate = flt(contract_row.rate)

	days_worked = sum(1 for f in DAY_FIELDS if flt(ts_row.get(f)) > 0)
	quantity = _convert_qty(days_worked, billing_frequency, ts.service_from_date, ts_row)
	amount = flt(rate) * flt(quantity)

	company = _get_company(hiring_contract)
	vat_rate = _get_item_vat_rate(equipment, company) if company else 0
	vat_amount = amount * vat_rate / 100 if vat_rate else 0

	return {
		"equipment_description": f"{ts_row.equipment_name or equipment} ({ts_row.vehicle_number or ''})".strip(),
		"uom": uom,
		"billing_frequency": billing_frequency,
		"rate": rate,
		"service_from": ts.service_from_date,
		"service_to": ts.service_to_date,
		"days_worked": days_worked,
		"quantity": quantity,
		"amount": amount,
		"vat_rate": vat_rate,
		"vat_amount": vat_amount,
	}


def _convert_qty(days_worked, billing_frequency, service_from_date, ts_row):
	if billing_frequency == "Daily":
		return days_worked

	if billing_frequency == "Monthly":
		d = getdate(service_from_date)
		days_in_month = calendar.monthrange(d.year, d.month)[1]
		return flt(days_worked) / days_in_month if days_in_month else days_worked

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


def create_purchase_receipt(srv_name):
	srv = frappe.get_doc("Service Receipt Voucher", srv_name)

	po_name = _get_linked_purchase_order(srv.hiring_contract)
	if not po_name:
		frappe.throw(
			_("No submitted Purchase Order was found for contract {0} — cannot create a Purchase Receipt.").format(
				frappe.bold(srv.hiring_contract)
			)
		)

	po_items_by_item_code = {
		row.item_code: row.name
		for row in frappe.get_all("Purchase Order Item", filters={"parent": po_name}, fields=["item_code", "name"])
	}

	def set_missing_values(source, target):
		target.supplier_delivery_note = srv.name
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
	# from the SRV's rows instead, so the quantities match exactly what was
	# approved on the voucher, not "whatever is still outstanding on the PO".
	pr.items = []

	for row in srv.timesheets:
		po_item_name = po_items_by_item_code.get(row.equipment)
		pr.append(
			"items",
			{
				"item_code": row.equipment,
				"item_name": row.equipment_description,
				"description": row.equipment_description,
				"uom": row.uom,
				"qty": row.quantity,
				"stock_qty": row.quantity,
				"rate": row.rate,
				"purchase_order": po_name,
				"purchase_order_item": po_item_name,
				"schedule_date": row.service_to,
			},
		)

	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr.name


def _get_linked_purchase_order(hiring_contract):
	fleet_hiring_request = frappe.db.get_value("Hiring Contract", hiring_contract, "fleet_hiring_request")
	if not fleet_hiring_request:
		return None
	return frappe.db.get_value(
		"Purchase Order",
		{"custom_reference_hiring_request": fleet_hiring_request, "docstatus": 1},
		"name",
	)
