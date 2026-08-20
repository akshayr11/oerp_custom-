# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Link-field search queries used when Purchase Order.purchase_type == "Contract".

A field's Link Filters property can only express static conditions on the target
doctype's own columns, so "supplier must have a submitted Vendor Contract" (an
EXISTS against another doctype) has to be a custom query.

Both queries only consider Vendor Contracts with docstatus = 1 and, when the
contract carries dates, ones currently in force.
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
def contract_vendors(doctype, txt, searchfield, start, page_len, filters):
	"""Suppliers holding at least one live, submitted Vendor Contract."""
	values = {
		"txt": f"%{txt}%",
		"_txt": txt.replace("%", ""),
		"start": start,
		"page_len": page_len,
	}

	return frappe.db.sql(
		f"""
		select s.name, s.supplier_name
		from `tabSupplier` s
		where s.disabled = 0
		  and exists (
		      select 1 from `tabVendor Contract` vc
		      where vc.vendor = s.name
		        and {_CONTRACT_LIVE}
		  )
		  and (s.name like %(txt)s or ifnull(s.supplier_name, '') like %(txt)s)
		order by
		    if(locate(%(_txt)s, s.name), locate(%(_txt)s, s.name), 99999),
		    s.name
		limit %(start)s, %(page_len)s
		""",
		values,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def contract_items(doctype, txt, searchfield, start, page_len, filters):
	"""Items listed on the selected supplier's live, submitted Vendor Contract(s).

	Returns nothing when no supplier is set yet — better an empty dropdown than
	the full item list, which would silently defeat the restriction.

	When a specific Vendor Contract is already chosen on the Purchase Order
	(custom_vendor_contract), results are narrowed to that document only, so a
	supplier with multiple active contracts can't mix items across them.
	"""
	filters = _as_dict(filters)
	vendor = filters.get("vendor") or filters.get("supplier")
	vendor_contract = filters.get("vendor_contract") or filters.get("custom_vendor_contract")

	if not vendor:
		return []

	conditions = ""
	values = {
		"vendor": vendor,
		"txt": f"%{txt}%",
		"_txt": txt.replace("%", ""),
		"start": start,
		"page_len": page_len,
	}

	if vendor_contract:
		conditions = "and vc.name = %(vendor_contract)s"
		values["vendor_contract"] = vendor_contract

	return frappe.db.sql(
		f"""
		select distinct i.name, i.item_name, i.item_group
		from `tabItem` i
		inner join `tabVendor Contract Items Table` vci on vci.item = i.name
		inner join `tabVendor Contract` vc on vc.name = vci.parent
		where i.disabled = 0
		  and ifnull(i.end_of_life, '2099-12-31') > curdate()
		  and vc.vendor = %(vendor)s
		  and vc.docstatus = 1
		  and ifnull(vc.contract_start_date, '1900-01-01') <= curdate()
		  and ifnull(vc.contract_end_date, '2999-12-31') >= curdate()
		  and (i.name like %(txt)s or ifnull(i.item_name, '') like %(txt)s)
		  {conditions}
		order by
		    if(locate(%(_txt)s, i.name), locate(%(_txt)s, i.name), 99999),
		    i.name
		limit %(start)s, %(page_len)s
		""",
		values,
	)


@frappe.whitelist()
def get_contract_item_details(vendor, item):
	"""Contracted rate/uom for one item, for autofill on the Purchase Order row."""
	if not (vendor and item):
		return {}

	rows = frappe.db.sql(
		"""
		select vci.rate, vci.uom, vci.currency, vc.name as contract
		from `tabVendor Contract Items Table` vci
		inner join `tabVendor Contract` vc on vc.name = vci.parent
		where vc.vendor = %(vendor)s
		  and vci.item = %(item)s
		  and vc.docstatus = 1
		  and ifnull(vc.contract_start_date, '1900-01-01') <= curdate()
		  and ifnull(vc.contract_end_date, '2999-12-31') >= curdate()
		order by ifnull(vc.contract_start_date, '1900-01-01') desc
		limit 1
		""",
		{"vendor": vendor, "item": item},
		as_dict=True,
	)

	return rows[0] if rows else {}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def vendor_contracts(doctype, txt, searchfield, start, page_len, filters):
	"""Live, submitted Vendor Contracts belonging to the selected supplier."""
	filters = _as_dict(filters)
	vendor = filters.get("vendor") or filters.get("supplier")

	if not vendor:
		return []

	return frappe.db.sql(
		"""
		select vc.name, vc.contract_title, vc.contract_end_date
		from `tabVendor Contract` vc
		where vc.vendor = %(vendor)s
		  and vc.docstatus = 1
		  and ifnull(vc.contract_start_date, '1900-01-01') <= curdate()
		  and ifnull(vc.contract_end_date, '2999-12-31') >= curdate()
		  and (vc.name like %(txt)s or ifnull(vc.contract_title, '') like %(txt)s)
		order by ifnull(vc.contract_start_date, '1900-01-01') desc, vc.name
		limit %(start)s, %(page_len)s
		""",
		{
			"vendor": vendor,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)


@frappe.whitelist()
def get_vendor_contract(vendor):
	"""Auto-pick the supplier's contract when there is exactly one in force.

	Returns "" when the supplier has several live contracts, so the user chooses
	rather than the form silently picking one for them.
	"""
	if not vendor:
		return ""

	names = _live_contracts_for(vendor)
	return names[0] if len(names) == 1 else ""


def _live_contracts_for(vendor):
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
