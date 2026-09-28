# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Fuel Card Transaction: balance-quantity tracking and fuel-price lookup.

Balance quantity resets every Refill Cycle (Weekly/Monthly/Yearly), anchored
to the card's own Issue Date — not the calendar month/week/year. E.g. a card
issued on the 15th, Monthly cycle, runs 15th-to-14th each month, not
1st-to-end-of-month. get_cycle_window() finds which such window a given date
falls into; get_used_quantity() sums this card's own transactions inside
that window (excluding cancelled ones, and excluding the transaction being
edited, so re-saving an existing one doesn't double-count itself); balance
= the card's Quantity (its per-cycle allowance) minus that sum.

Fuel Price is looked up from Fuel Card Prices by Fuel Type + the card's own
Cost Center + the transaction date's Month/Year, requiring an Active price
record — deliberately not defaulting to 0 or the nearest available price,
since a missing/wrong price on a fuel transaction is exactly the kind of
mistake that should block the save, not fall through silently.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, add_years, flt, getdate

DAY = "Weekly"
MONTH = "Monthly"
YEAR = "Yearly"


def get_cycle_window(issue_date, refill_cycle, reference_date):
	issue = getdate(issue_date)
	ref = getdate(reference_date)

	if ref < issue:
		return issue, issue

	if refill_cycle == DAY:
		days_since = (ref - issue).days
		cycle_start = add_days(issue, (days_since // 7) * 7)
		cycle_end = add_days(cycle_start, 6)
	elif refill_cycle == MONTH:
		months_since = (ref.year - issue.year) * 12 + (ref.month - issue.month)
		if ref.day < issue.day:
			months_since -= 1
		cycle_start = add_months(issue, months_since)
		cycle_end = add_days(add_months(cycle_start, 1), -1)
	elif refill_cycle == YEAR:
		years_since = ref.year - issue.year
		if (ref.month, ref.day) < (issue.month, issue.day):
			years_since -= 1
		cycle_start = add_years(issue, years_since)
		cycle_end = add_days(add_years(cycle_start, 1), -1)
	else:
		cycle_start = cycle_end = ref

	return cycle_start, cycle_end


def get_used_quantity(fuel_card, cycle_start, cycle_end, exclude_name=None):
	filters = {
		"fuel_card": fuel_card,
		"transaction_date": ["between", [cycle_start, cycle_end]],
		"docstatus": ["<", 2],
	}
	if exclude_name:
		filters["name"] = ["!=", exclude_name]

	rows = frappe.get_all("Fuel Card Transaction", filters=filters, fields=["quantity"])
	return sum(flt(r.quantity) for r in rows)


def get_balance_before(fuel_card, transaction_date, exclude_name=None):
	"""Balance available at the start of this transaction — before its own
	Quantity is deducted.
	"""
	card = frappe.db.get_value(
		"Fuel Card Master", fuel_card, ["issue_date", "refill_cycle", "quantity"], as_dict=True
	)
	if not card:
		frappe.throw(_("Fuel Card {0} not found.").format(fuel_card))

	cycle_start, cycle_end = get_cycle_window(card.issue_date, card.refill_cycle, transaction_date)
	used = get_used_quantity(fuel_card, cycle_start, cycle_end, exclude_name)
	return flt(card.quantity) - used


@frappe.whitelist()
def get_balance_preview(fuel_card, transaction_date, quantity=0, exclude_name=None):
	balance_before = get_balance_before(fuel_card, transaction_date, exclude_name)
	return balance_before - flt(quantity)


def get_fuel_price(fuel_type, cost_center, transaction_date):
	d = getdate(transaction_date)
	price = frappe.db.get_value(
		"Fuel Card Prices",
		{
			"fuel_type": fuel_type,
			"cost_center": cost_center,
			"month": d.strftime("%B"),
			"year": d.year,
			"current_status": "Active",
		},
		"price",
	)
	if price is None:
		frappe.throw(
			_("No active Fuel Card Price found for {0} at {1} in {2} {3}.").format(
				frappe.bold(fuel_type), frappe.bold(cost_center), d.strftime("%B"), d.year
			)
		)
	return flt(price)


@frappe.whitelist()
def get_fuel_price_for_card(fuel_card, transaction_date):
	fuel_type, cost_center = frappe.db.get_value("Fuel Card Master", fuel_card, ["fuel_type", "cost_center"])
	return get_fuel_price(fuel_type, cost_center, transaction_date)


@frappe.whitelist()
def get_card_equipment(fuel_card):
	"""Equipment linked to this card, for the client to decide whether to
	auto-fill (exactly one) or restrict selection to this list (more than
	one, card not Open) or leave the Equipment field unrestricted (none
	linked at all, or the card is Open).
	"""
	return frappe.get_all(
		"Fuel Card Equipment", filters={"parent": fuel_card, "parenttype": "Fuel Card Master"}, pluck="equipment"
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def equipment_query(doctype, txt, searchfield, start, page_len, filters):
	"""Backs the Equipment field's own query on the transaction — a
	non-Open card with linked equipment restricts selection to that list;
	an Open card, or one with nothing linked, allows any equipment.
	"""
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	fuel_card = filters.get("fuel_card")
	linked = get_card_equipment(fuel_card) if fuel_card else []

	values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}
	restriction = ""
	if linked:
		restriction = "and name in %(linked)s"
		values["linked"] = linked

	return frappe.db.sql(
		f"""
		select name, item_name
		from `tabItem`
		where name like %(txt)s
		{restriction}
		order by name
		limit %(start)s, %(page_len)s
		""",
		values,
	)
