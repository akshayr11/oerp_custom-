# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Server-side backing for the Vendor Contract link on Purchase Order Item.

The grid query in oerp_custom.queries only shapes the dropdown. Anything that
does not go through the form — REST API, Data Import, bench console — can still
write a contract belonging to a different supplier, or one that does not carry
the row's item, so the same two conditions are re-checked here on validate.

This does not police which items may be ordered. An item with no contract is
perfectly fine; its row simply keeps a blank contract. The only thing rejected
is a contract that contradicts the row it sits on.

Where a row leaves the contract blank and exactly one of the supplier's live
contracts carries that item, it is filled in here — so API-created orders end
up with the same reference the form would have set.

Batched queries only: two lookups regardless of item row count.
"""

import frappe
from frappe import _

from oerp_custom.queries import _live_contracts_for

# Fieldname of the Link (to Vendor Contract) custom field on Purchase Order Item.
CONTRACT_FIELD = "custom_vendor_contract"


def validate_contract_scope(doc, method=None):
	rows = doc.get("items") or []
	if not rows:
		return

	if not doc.supplier:
		# Nothing to match against — drop stale links rather than leave a
		# contract pointing at a supplier this order no longer names.
		for row in rows:
			row.set(CONTRACT_FIELD, None)
		return

	contracts = _live_contracts_for(doc.supplier)

	if not contracts:
		_reject_orphans(doc, rows)
		return

	_apply_contracts(doc, rows, _contracts_by_item(contracts))


def _reject_orphans(doc, rows):
	"""Supplier has no live contract at all, so no row may name one."""
	named = [
		_("Row {0}: {1}").format(row.idx, row.get(CONTRACT_FIELD))
		for row in rows
		if row.get(CONTRACT_FIELD)
	]

	if named:
		frappe.throw(
			_("Supplier {0} has no submitted Vendor Contract in force today, "
			  "so these rows cannot reference one:<br>{1}").format(
				frappe.bold(doc.supplier), "<br>".join(named)
			),
			title=_("No Active Vendor Contract"),
		)


def _contracts_by_item(contracts):
	"""{item_code: [contract, ...]} across the supplier's live contracts."""
	rows = frappe.get_all(
		"Vendor Contract Items Table",
		filters={"parent": ("in", contracts), "parenttype": "Vendor Contract"},
		fields=["parent", "item"],
	)

	mapping = {}
	for row in rows:
		mapping.setdefault(row.item, []).append(row.parent)
	return mapping


def _apply_contracts(doc, rows, by_item):
	mismatched = []

	for row in rows:
		if not row.item_code:
			row.set(CONTRACT_FIELD, None)
			continue

		eligible = by_item.get(row.item_code, [])
		selected = row.get(CONTRACT_FIELD)

		if selected:
			if selected not in eligible:
				mismatched.append(
					_("Row {0}: {1} is not on contract {2}").format(
						row.idx, row.item_code, selected
					)
				)
		elif len(eligible) == 1:
			# Only one live contract covers this item — no reason to make
			# anyone pick it by hand.
			row.set(CONTRACT_FIELD, eligible[0])

	if mismatched:
		frappe.throw(
			_("The Vendor Contract on these rows does not cover the row's item "
			  "for supplier {0}, or is not in force today:<br>{1}").format(
				frappe.bold(doc.supplier), "<br>".join(mismatched)
			),
			title=_("Contract Mismatch"),
		)
