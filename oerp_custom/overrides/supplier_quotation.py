# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""One Supplier Quotation per (Request for Quotation, Supplier) pair.

A supplier may only quote once against a given RFQ — if a second Supplier
Quotation for the same supplier, against an RFQ they already quoted, needs
raising, the existing one should be amended/cancelled instead. Only rows
that actually trace back to an RFQ are checked; quotations entered directly
(no request_for_quotation on any row) are unaffected.
"""

import frappe
from frappe import _


def validate_no_duplicate_rfq_quotation(doc, method=None):
	if not doc.supplier:
		return

	rfq_names = {row.request_for_quotation for row in doc.get("items") or [] if row.request_for_quotation}
	if not rfq_names:
		return

	for rfq_name in rfq_names:
		existing = frappe.db.sql(
			"""
			SELECT DISTINCT sq.name
			FROM `tabSupplier Quotation` sq
			INNER JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
			WHERE sq.supplier = %(supplier)s
				AND sqi.request_for_quotation = %(rfq_name)s
				AND sq.name != %(name)s
				AND sq.docstatus != 2
			""",
			{"supplier": doc.supplier, "rfq_name": rfq_name, "name": doc.name or ""},
			as_dict=True,
		)
		if existing:
			frappe.throw(
				_(
					"{0} already has a Supplier Quotation ({1}) against {2}. "
					"Amend or cancel that one instead of creating another."
				).format(
					frappe.bold(doc.supplier),
					frappe.bold(existing[0].name),
					frappe.bold(rfq_name),
				),
				title=_("Duplicate Supplier Quotation"),
			)
