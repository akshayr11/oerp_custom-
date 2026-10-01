# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Purchase Receipts auto-created from a Hiring Receipt (see
overrides/hiring_receipt.py) carry their own custom Net Amount per item
(Total + OT - Deduction), separate from ERPNext's own net_amount (Qty x
Rate). On request, each item row's standard "Net Amount (<currency>)" and
"Net Amount (Company Currency) (<currency>)" fields (net_amount/
base_net_amount) are made to display that same custom figure.

This is display-only on the item row, by design — it runs as a doc_events
hook (see hooks.py), which Document.hook always runs AFTER the controller's
own validate() (frappe/model/document.py: compose() calls fn, then hooks),
i.e. after ERPNext's calculate_taxes_and_totals() has already summed the
ORIGINAL Qty x Rate net_amount values into the document's own Net Total/
Grand Total. Overriding the item field here, after that sum was taken,
doesn't retrigger a recalculation, so the document's totals and the
accounting entries posted on submit keep following Qty x Rate, untouched.
"""

from frappe.utils import flt


def sync_net_amount_display(doc, method=None):
	if not doc.custom_hiring_receipt:
		return

	for row in doc.get("items") or []:
		if row.custom_net_amount is None:
			continue
		row.net_amount = flt(row.custom_net_amount)
		row.base_net_amount = flt(row.custom_net_amount) * flt(doc.conversion_rate or 1)
