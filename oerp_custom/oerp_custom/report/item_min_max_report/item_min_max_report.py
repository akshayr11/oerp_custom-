# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Item Min Max Report.

Min/Max Qty come from the per-warehouse "Reorder Levels" child table on Item
(Item Reorder: warehouse / warehouse_reorder_level / warehouse_reorder_qty) —
the same table Material Request uses for its own min/max qty lookup — not
from Item's own flat min_qty/max_qty fields, since those don't vary by
warehouse.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Description"), "fieldname": "description", "fieldtype": "Small Text", "width": 220},
		{"label": _("Item Category"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Store"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Min Qty"), "fieldname": "min_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Max Qty"), "fieldname": "max_qty", "fieldtype": "Float", "width": 100},
	]


def get_data(filters):
	conditions = ["item.disabled = 0"]
	values = {}

	if filters.get("warehouse"):
		conditions.append("ir.warehouse = %(warehouse)s")
		values["warehouse"] = filters.warehouse

	if filters.get("item_code"):
		conditions.append("item.item_code = %(item_code)s")
		values["item_code"] = filters.item_code

	if filters.get("item_group"):
		conditions.append("item.item_group = %(item_group)s")
		values["item_group"] = filters.item_group

	condition_str = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			item.item_code AS item_code,
			item.item_name AS item_name,
			item.description AS description,
			item.item_group AS item_group,
			ir.warehouse AS warehouse,
			ir.warehouse_reorder_level AS min_qty,
			ir.warehouse_reorder_qty AS max_qty
		FROM `tabItem` item
		INNER JOIN `tabItem Reorder` ir
			ON ir.parent = item.name AND ir.parenttype = 'Item'
		WHERE {condition_str}
		ORDER BY item.item_code, ir.warehouse
		""",
		values,
		as_dict=1,
	)
