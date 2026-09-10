# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Service requests and purchase-type naming.

Material Request
----------------
Ticking **By Service** (`custom_by_service_`) turns the document into a service
request:

    * the series becomes  SER-MR-.YYYY.-
    * `custom_service_type` becomes mandatory
    * every item row must be a service item (Maintain Stock off)

Purchase Order
--------------
The series follows `purchase_type`:

    Service   ->  PUR-SER-.YYYY.-
    others    ->  whatever the user picked (default PUR-ORD-.YYYY.-)

All of it is enforced here, so REST, Data Import and the bench console get the
same result as the form — the client scripts only make the form pleasant.

Timing matters: frappe names a document BEFORE validate runs on insert, so the
series is fixed in `before_insert` (early enough to shape the name) and only
verified in `validate` (where a mismatch after naming becomes a warning, never
a rename — renaming a numbered document would orphan every link to it).
"""

import frappe
from frappe import _

MR_SERVICE_SERIES = "SER-MR-.YYYY.-"

PO_SERIES_BY_TYPE = {
	"Service": "PUR-SER-.YYYY.-",
}


# ---------------------------------------------------------------------------
# Material Request
# ---------------------------------------------------------------------------


def before_insert_material_request(doc, method=None):
	"""Runs before frappe names the document — the last moment the series
	can still shape the name."""
	if doc.get("custom_by_service_"):
		doc.naming_series = MR_SERVICE_SERIES


def validate_material_request(doc, method=None):
	if not doc.get("custom_by_service_"):
		return

	_apply_series(doc, MR_SERVICE_SERIES)

	if not doc.get("custom_service_type"):
		frappe.throw(
			_("Service Type is mandatory on a service request."),
			title=_("Service Type Missing"),
		)

	_ensure_service_items(doc)


def _ensure_service_items(doc):
	"""Every row on a service request must be a service (non-stock) item.

	One batched lookup regardless of row count.
	"""
	item_codes = list({row.item_code for row in doc.get("items", []) if row.item_code})
	if not item_codes:
		return

	stock_items = set(
		frappe.get_all(
			"Item",
			filters={"name": ("in", item_codes), "is_stock_item": 1},
			pluck="name",
		)
	)

	offending = [
		_("Row {0}: {1}").format(row.idx, row.item_code)
		for row in doc.get("items", [])
		if row.item_code in stock_items
	]
	if offending:
		frappe.throw(
			_("A service request can only carry service items (Maintain Stock off). "
			  "These rows are stock items:<br>{0}").format("<br>".join(offending)),
			title=_("Not a Service Item"),
		)


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------


def before_insert_purchase_order(doc, method=None):
	series = PO_SERIES_BY_TYPE.get(doc.get("purchase_type"))
	if series:
		doc.naming_series = series


def apply_po_naming(doc, method=None):
	series = PO_SERIES_BY_TYPE.get(doc.get("purchase_type"))
	if series:
		_apply_series(doc, series)

	if doc.get("purchase_type") != "Service" and doc.get("custom_service_type"):
		# A leftover service type on a material/asset order is misleading.
		doc.custom_service_type = None


# ---------------------------------------------------------------------------
# Material Request -> Purchase Order carry-over
# ---------------------------------------------------------------------------


@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None, args=None):
	"""Wrapper around ERPNext's mapper.

	A Purchase Order raised from a service Material Request arrives already
	typed: purchase_type = Service, the Service Type copied across, and the
	PUR-SER series set — the buyer does not have to remember any of it.
	"""
	from erpnext.stock.doctype.material_request.material_request import (
		make_purchase_order as _make_purchase_order,
	)

	doc = _make_purchase_order(source_name, target_doc=target_doc, args=args)

	if frappe.db.get_value("Material Request", source_name, "custom_by_service_"):
		doc.purchase_type = "Service"
		doc.custom_service_type = frappe.db.get_value(
			"Material Request", source_name, "custom_service_type"
		)
		_apply_series(doc, PO_SERIES_BY_TYPE["Service"])

	return doc


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


def _apply_series(doc, series):
	"""Set the series on a not-yet-named document.

	After naming, the series field may still be corrected for display, but the
	name itself is left alone: renaming a numbered document would orphan every
	link that already points at it.
	"""
	if doc.get("__islocal") or not doc.get("name") or doc.get("name", "").startswith("new-"):
		doc.naming_series = series
	elif doc.get("naming_series") != series:
		frappe.msgprint(
			_("This document was numbered under {0}; the series is not changed after naming. "
			  "New documents will use {1}.").format(
				frappe.bold(doc.get("naming_series") or "?"), frappe.bold(series)
			),
			indicator="orange",
			alert=True,
		)