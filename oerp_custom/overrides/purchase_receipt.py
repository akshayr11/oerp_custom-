# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Purchase Receipts auto-created from a Hiring Receipt (see
overrides/hiring_receipt.py) carry their own custom Net Amount per item
(Total + OT - Deduction), separate from ERPNext's own net_amount (Qty x
Rate).

Per explicit confirmation, this now drives the REAL document totals, not
just item-row display: Net Total, any "On Net Total" tax row (e.g. VAT),
Grand Total and Rounded Total are all recomputed from the sum of each
item's custom_net_amount — i.e. including OT and Deduction — instead of
Qty x Rate. That means the accounting entries posted on submit follow
custom_net_amount too.

This runs as a doc_events hook (see hooks.py), which Document.hook always
runs AFTER the controller's own validate() (frappe/model/document.py:
compose() calls fn, then hooks) — i.e. after ERPNext's own
calculate_taxes_and_totals() has already summed the ORIGINAL Qty x Rate
values. Item.amount/rate/qty themselves are left untouched (so the Items
table itself still reads Qty x Rate) — only net_amount and everything
derived from it (taxes, net/grand/rounded totals) are overridden.

Only "On Net Total" tax rows are recomputed here — the only charge_type
actually in use for the VAT row this exists for. Other charge types
(Actual, On Previous Row Amount/Total, On Item Quantity) are left as
ERPNext already computed them, since they don't derive from Net Total.
"""

from frappe.utils import flt

from oerp_custom.overrides.hiring_receipt import _get_item_vat_rate


def sync_net_amount_display(doc, method=None):
	if not doc.custom_hiring_receipt:
		return

	for row in doc.get("items") or []:
		if row.custom_net_amount is None:
			continue
		row.net_amount = flt(row.custom_net_amount)
		row.base_net_amount = flt(row.custom_net_amount) * flt(doc.conversion_rate or 1)

		vat_rate = _get_item_vat_rate(row.item_code, doc.company) if doc.company else 0
		row.custom_vat_amount = flt(row.custom_net_amount) * flt(vat_rate) / 100 if vat_rate else 0
		row.custom_net_amount_with_vat = flt(row.custom_net_amount) + flt(row.custom_vat_amount)

	_recalculate_totals_from_net_amount(doc)


def _recalculate_totals_from_net_amount(doc):
	items = doc.get("items") or []
	net_total = flt(sum(flt(row.net_amount) for row in items), doc.precision("net_total"))
	base_net_total = flt(sum(flt(row.base_net_amount) for row in items), doc.precision("base_net_total"))

	doc.total = net_total
	doc.base_total = base_net_total
	doc.net_total = net_total
	doc.base_net_total = base_net_total

	total_taxes = 0.0
	base_total_taxes = 0.0
	running_total = net_total
	running_base_total = base_net_total

	for tax in doc.get("taxes") or []:
		if tax.charge_type == "On Net Total":
			tax.tax_amount = flt(net_total * flt(tax.rate) / 100, tax.precision("tax_amount"))
			tax.base_tax_amount = flt(
				base_net_total * flt(tax.rate) / 100, tax.precision("base_tax_amount")
			)

		tax.tax_amount_after_discount_amount = tax.tax_amount
		tax.base_tax_amount_after_discount_amount = tax.base_tax_amount

		running_total += flt(tax.tax_amount)
		running_base_total += flt(tax.base_tax_amount)
		tax.total = flt(running_total, tax.precision("total"))
		tax.base_total = flt(running_base_total, tax.precision("base_total"))

		total_taxes += flt(tax.tax_amount)
		base_total_taxes += flt(tax.base_tax_amount)

	doc.taxes_and_charges_added = flt(total_taxes, doc.precision("taxes_and_charges_added"))
	doc.base_taxes_and_charges_added = flt(base_total_taxes, doc.precision("base_taxes_and_charges_added"))
	doc.total_taxes_and_charges = flt(total_taxes, doc.precision("total_taxes_and_charges"))
	doc.base_total_taxes_and_charges = flt(
		base_total_taxes, doc.precision("base_total_taxes_and_charges")
	)

	doc.grand_total = flt(net_total + total_taxes, doc.precision("grand_total"))
	doc.base_grand_total = flt(base_net_total + base_total_taxes, doc.precision("base_grand_total"))

	if doc.get("disable_rounded_total"):
		doc.rounded_total = doc.grand_total
		doc.base_rounded_total = doc.base_grand_total
		doc.rounding_adjustment = 0
		doc.base_rounding_adjustment = 0
	else:
		doc.rounded_total = round(doc.grand_total)
		doc.base_rounded_total = round(doc.base_grand_total)
		doc.rounding_adjustment = flt(
			doc.rounded_total - doc.grand_total, doc.precision("rounding_adjustment")
		)
		doc.base_rounding_adjustment = flt(
			doc.base_rounded_total - doc.base_grand_total, doc.precision("base_rounding_adjustment")
		)
