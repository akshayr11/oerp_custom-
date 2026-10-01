# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Hiring Request Tracking Report.

One row per Purchase Receipt Item, tracing that line all the way back up
the chain it came from: Fleet Hiring Request -> Hiring Contract -> Hiring
Receipt -> Purchase Receipt. From Date/To Date (both optional) filter on
the Fleet Hiring Request's own Request Date, not the Purchase Receipt's —
a request with no Purchase Receipt yet simply won't have a row, since this
report is specifically about what's reached that far.

Only submitted (non-cancelled) Purchase Receipts are included.
"""

import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Fleet Hiring Request", "fieldname": "fleet_hiring_request", "fieldtype": "Link", "options": "Fleet Hiring Request", "width": 160},
		{"label": "FHR Status", "fieldname": "fhr_status", "fieldtype": "Data", "width": 100},
		{"label": "Request Date", "fieldname": "request_date", "fieldtype": "Date", "width": 100},
		{"label": "Cost Center", "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 120},
		{"label": "Requested By", "fieldname": "requested_by", "fieldtype": "Link", "options": "User", "width": 120},
		{"label": "Hiring Contract", "fieldname": "hiring_contract", "fieldtype": "Link", "options": "Hiring Contract", "width": 150},
		{"label": "Vendor", "fieldname": "vendor_name", "fieldtype": "Data", "width": 140},
		{"label": "Purchase Order", "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 140},
		{"label": "Hiring Receipt", "fieldname": "hiring_receipt", "fieldtype": "Link", "options": "Hiring Receipt", "width": 150},
		{"label": "HR Status", "fieldname": "hr_status", "fieldtype": "Data", "width": 100},
		{"label": "Service Month", "fieldname": "service_month", "fieldtype": "Data", "width": 100},
		{"label": "Service Year", "fieldname": "service_year", "fieldtype": "Int", "width": 90},
		{"label": "Purchase Receipt", "fieldname": "purchase_receipt", "fieldtype": "Link", "options": "Purchase Receipt", "width": 150},
		{"label": "PR Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": "Equipment", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": "Equipment Name", "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "options": "currency", "width": 100},
		{"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": "OT Amount", "fieldname": "ot_amount", "fieldtype": "Currency", "options": "currency", "width": 100},
		{"label": "Deduction Amount", "fieldname": "deduction_amount", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": "Net Amount", "fieldname": "net_amount", "fieldtype": "Currency", "options": "currency", "width": 110},
		{"label": "VAT Amount", "fieldname": "vat_amount", "fieldtype": "Currency", "options": "currency", "width": 100},
		{"label": "Net Amount (Incl. VAT)", "fieldname": "net_amount_with_vat", "fieldtype": "Currency", "options": "currency", "width": 140},
	]


def get_data(filters):
	conditions = ["pr.docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("fhr.request_date >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("fhr.request_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	condition_str = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			fhr.name AS fleet_hiring_request,
			fhr.workflow_state AS fhr_status,
			fhr.request_date AS request_date,
			fhr.cost_center AS cost_center,
			fhr.requested_by AS requested_by,
			hc.name AS hiring_contract,
			hc.vendor_name AS vendor_name,
			hc.purchase_order AS purchase_order,
			hr.name AS hiring_receipt,
			hr.workflow_state AS hr_status,
			hr.service_month AS service_month,
			hr.service_year AS service_year,
			pr.name AS purchase_receipt,
			pr.posting_date AS posting_date,
			pri.item_code AS item_code,
			pri.item_name AS item_name,
			pri.uom AS uom,
			pri.qty AS qty,
			pri.rate AS rate,
			pri.custom_total_amount AS total_amount,
			pri.custom_ot_amount AS ot_amount,
			pri.custom_deduction_amount AS deduction_amount,
			pri.custom_net_amount AS net_amount,
			pri.custom_vat_amount AS vat_amount,
			pri.custom_net_amount_with_vat AS net_amount_with_vat
		FROM `tabPurchase Receipt Item` pri
		INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
		INNER JOIN `tabHiring Receipt` hr ON hr.name = pr.custom_hiring_receipt
		INNER JOIN `tabHiring Contract` hc ON hc.name = hr.hiring_contract
		INNER JOIN `tabFleet Hiring Request` fhr ON fhr.name = hc.fleet_hiring_request
		WHERE {condition_str}
		ORDER BY fhr.request_date DESC, pr.posting_date DESC, pri.idx
		""",
		values,
		as_dict=1,
	)
