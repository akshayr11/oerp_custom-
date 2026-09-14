# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Vendor Contract lookups for the Purchase Order Item grid.

Each Purchase Order Item row carries its own Vendor Contract link
(`custom_vendor_contract`). Two things are needed for it:

    * a search query that narrows the dropdown to contracts belonging to the
      header's supplier which actually list that row's item
    * a lookup that resolves the matching contract outright when there is only
      one, so the user does not have to pick the obvious answer

A field's Link Filters property can only express static conditions on the
target doctype's own columns, so "contract belongs to this supplier and carries
this item" (an EXISTS against a child table) has to be a custom query.

Only Vendor Contracts with docstatus = 1 count and, when the contract carries
dates, only ones currently in force.
"""

import json

import frappe

# Contract must be submitted and, if dated, currently in force.
_CONTRACT_LIVE = """
	vc.docstatus = 1
	and ifnull(vc.contract_start_date, '1900-01-01') <= curdate()
	and ifnull(vc.contract_end_date, '2999-12-31') >= curdate()
"""


def _as_dict(filters):
	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	return filters or {}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def vendor_contracts(doctype, txt, searchfield, start, page_len, filters):
	"""Live contracts for a supplier — and, if an item is passed, only the ones
	that list that item.

	This backs the Vendor Contract link inside the Purchase Order Item grid.
	`vendor` comes from the header's supplier, `item` from the row being
	edited. With no supplier, nothing is returned: better an empty dropdown
	than every contract in the system.
	"""
	filters = _as_dict(filters)
	vendor = filters.get("vendor") or filters.get("supplier")
	item = filters.get("item") or filters.get("item_code")

	if not vendor:
		return []

	values = {
		"vendor": vendor,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	}

	item_condition = ""
	if item:
		item_condition = """
		  and exists (
		      select 1 from `tabVendor Contract Items Table` vci
		      where vci.parent = vc.name
		        and vci.parenttype = 'Vendor Contract'
		        and vci.item = %(item)s
		  )
		"""
		values["item"] = item

	return frappe.db.sql(
		f"""
		select vc.name, vc.contract_title, vc.contract_end_date
		from `tabVendor Contract` vc
		where vc.vendor = %(vendor)s
		  and {_CONTRACT_LIVE}
		  {item_condition}
		  and (vc.name like %(txt)s or ifnull(vc.contract_title, '') like %(txt)s)
		order by ifnull(vc.contract_start_date, '1900-01-01') desc, vc.name
		limit %(start)s, %(page_len)s
		""",
		values,
	)


@frappe.whitelist()
def get_contract_item_details(vendor, item, vendor_contract=None):
	"""Resolve the Vendor Contract for one supplier/item pair.

	Returns:

	    contract        the contract to write to the row, or "" when the user
	                    must choose (several live contracts carry this item)
	    contract_count  how many live contracts of this supplier carry it
	    rate, uom,      the contracted terms for that item — returned for
	    currency        callers that want them, unused by the grid today

	Passing `vendor_contract` pins the answer to that contract. If that
	contract does not carry the item, contract_count comes back 0 with
	mismatch set, so the caller can flag it rather than keep a stale link.
	"""
	if not (vendor and item):
		return {}

	rows = frappe.db.sql(
		f"""
		select vc.name as contract, vci.rate, vci.uom, vci.currency,
		       ifnull(vc.contract_start_date, '1900-01-01') as start_date
		from `tabVendor Contract Items Table` vci
		inner join `tabVendor Contract` vc on vc.name = vci.parent
		where vci.parenttype = 'Vendor Contract'
		  and vci.item = %(item)s
		  and vc.vendor = %(vendor)s
		  and {_CONTRACT_LIVE}
		order by start_date desc, vc.name
		""",
		{"vendor": vendor, "item": item},
		as_dict=True,
	)

	if vendor_contract:
		pinned = [r for r in rows if r.contract == vendor_contract]
		if not pinned:
			return {"contract": "", "contract_count": 0, "mismatch": 1}
		row = pinned[0]
		return {
			"contract": row.contract,
			"rate": row.rate,
			"uom": row.uom,
			"currency": row.currency,
			"contract_count": len(rows),
		}

	if not rows:
		return {"contract": "", "contract_count": 0}

	if len(rows) > 1:
		# Ambiguous — let the user pick from the (already filtered) dropdown
		# rather than guessing on their behalf.
		return {"contract": "", "contract_count": len(rows)}

	row = rows[0]
	return {
		"contract": row.contract,
		"rate": row.rate,
		"uom": row.uom,
		"currency": row.currency,
		"contract_count": 1,
	}


def _live_contracts_for(vendor):
	"""All live, submitted contract names for a supplier."""
	return frappe.db.sql_list(
		"""
		select name from `tabVendor Contract`
		where vendor = %(vendor)s
		  and docstatus = 1
		  and ifnull(contract_start_date, '1900-01-01') <= curdate()
		  and ifnull(contract_end_date, '2999-12-31') >= curdate()
		order by ifnull(contract_start_date, '1900-01-01') desc
		""",
		{"vendor": vendor},
	)




@frappe.whitelist()
def get_contract_item_rate(contract, item):
	"""Return the contracted rate for `item` on `contract`, or None."""
	rate = frappe.db.get_value(
		"Vendor Contract Items Table",
		{"parent": contract, "item": item},
		"rate",
	)
	return rate
