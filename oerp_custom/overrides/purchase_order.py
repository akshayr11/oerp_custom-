# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Server-side enforcement of the Contract purchase type.

The link queries in oerp_custom.queries only shape the dropdowns. Anything that
does not go through the form — REST API, Data Import, a draft saved before this
rule existed, bench console — can still write an off-contract supplier or item,
so the same rules are re-checked on validate.

Batched queries only: two lookups regardless of item row count.
"""

import frappe
from frappe import _

from oerp_custom.queries import _live_contracts_for

# Fieldname of the Link (to Vendor Contract) custom field on Purchase Order.
CONTRACT_FIELD = "custom_vendor_contract"


def validate_contract_scope(doc, method=None):
	if doc.get("purchase_type") != "Contract":
		return

	if not doc.supplier:
		return  # the mandatory check on supplier fires on its own

	contracts = _live_contracts_for(doc.supplier)

	if not contracts:
		frappe.throw(
			_("Supplier {0} has no submitted Vendor Contract in force today. "
			  "Purchase Type 'Contract' requires an active contract.").format(
				frappe.bold(doc.supplier)
			),
			title=_("No Active Vendor Contract"),
		)

	_validate_contract_link(doc, contracts)
	_validate_items(doc, contracts)


def _validate_contract_link(doc, contracts):
	"""If the Vendor Contract field is set, it must be one of this supplier's."""
	selected = doc.get(CONTRACT_FIELD)

	if not selected:
		# Fill it in when the supplier has exactly one contract, so API-created
		# orders end up with the same reference the form would have set.
		if len(contracts) == 1:
			doc.set(CONTRACT_FIELD, contracts[0])
		return

	if selected not in contracts:
		frappe.throw(
			_("Vendor Contract {0} does not belong to supplier {1}, "
			  "or is not in force today.").format(
				frappe.bold(selected), frappe.bold(doc.supplier)
			),
			title=_("Contract Mismatch"),
		)


def _validate_items(doc, contracts):
	"""Every item row must appear on the supplier's contract.

	Scoped to the single selected contract when one is set, otherwise to any of
	the supplier's live contracts.
	"""
	scope = [doc.get(CONTRACT_FIELD)] if doc.get(CONTRACT_FIELD) else contracts

	allowed = set(
		frappe.get_all(
			"Vendor Contract Items Table",
			filters={"parent": ("in", scope), "parenttype": "Vendor Contract"},
			pluck="item",
		)
	)

	invalid = [
		_("Row {0}: {1}").format(row.idx, row.item_code)
		for row in doc.items
		if row.item_code and row.item_code not in allowed
	]

	if invalid:
		frappe.throw(
			_("These items are not on {0}'s Vendor Contract:<br>{1}").format(
				frappe.bold(doc.supplier), "<br>".join(invalid)
			),
			title=_("Item Not Under Contract"),
		)
