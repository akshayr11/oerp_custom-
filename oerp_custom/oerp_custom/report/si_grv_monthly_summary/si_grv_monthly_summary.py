# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe

MONTH_NAME_TO_NUM = {
	"January": 1,
	"February": 2,
	"March": 3,
	"April": 4,
	"May": 5,
	"June": 6,
	"July": 7,
	"August": 8,
	"September": 9,
	"October": 10,
	"November": 11,
	"December": 12,
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Cost Center", "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 150},
		{"label": "Transaction Month/Year", "fieldname": "month_year", "fieldtype": "Data", "width": 130},
		{"label": "Asset GRV Value", "fieldname": "asset_value", "fieldtype": "Currency", "width": 130},
		{"label": "Material GRV Value", "fieldname": "material_value", "fieldtype": "Currency", "width": 130},
		{"label": "Service GRV Value", "fieldname": "service_value", "fieldtype": "Currency", "width": 130},
		{"label": "Stock Issue Value", "fieldname": "stock_issue_value", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	year = filters.get("year")
	months_list = filters.get("months") or []

	month_numbers = [str(MONTH_NAME_TO_NUM[m]) for m in months_list if m in MONTH_NAME_TO_NUM]

	if not year or not month_numbers:
		return []

	months_str = ",".join(month_numbers)

	# pri.amount is the item's pre-tax net amount. GRV value must reflect the
	# PR's Grand Total (after taxes and charges), so each item's amount is
	# scaled by that PR's (base_grand_total / base_net_total) ratio before
	# being bucketed into asset/material/service — this prorates the
	# document-level tax down to item level without needing itemised tax
	# breakup, and the category totals still sum to the PR's actual Grand Total.
	query = """
		WITH grv AS (
			SELECT
				pri.cost_center AS cost_center,
				YEAR(pr.posting_date) AS year,
				MONTH(pr.posting_date) AS month,
				SUM(CASE WHEN it.is_fixed_asset = 1
					THEN pri.amount * (pr.base_grand_total / NULLIF(pr.base_net_total, 0))
					ELSE 0 END) AS asset_value,
				SUM(CASE WHEN it.is_fixed_asset = 0 AND it.is_stock_item = 1
					THEN pri.amount * (pr.base_grand_total / NULLIF(pr.base_net_total, 0))
					ELSE 0 END) AS material_value,
				SUM(CASE WHEN it.is_fixed_asset = 0 AND it.is_stock_item = 0
					THEN pri.amount * (pr.base_grand_total / NULLIF(pr.base_net_total, 0))
					ELSE 0 END) AS service_value
			FROM `tabPurchase Receipt Item` pri
			INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			LEFT JOIN `tabItem` it ON it.name = pri.item_code
			WHERE pr.docstatus = 1
				AND YEAR(pr.posting_date) = %(year)s
				AND FIND_IN_SET(MONTH(pr.posting_date), %(months)s)
			GROUP BY pri.cost_center, YEAR(pr.posting_date), MONTH(pr.posting_date)
		),
		si AS (
			SELECT
				sed.cost_center AS cost_center,
				YEAR(se.posting_date) AS year,
				MONTH(se.posting_date) AS month,
				SUM(sed.amount) AS stock_issue_value
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.docstatus = 1
				AND se.purpose = 'Material Issue'
				AND YEAR(se.posting_date) = %(year)s
				AND FIND_IN_SET(MONTH(se.posting_date), %(months)s)
			GROUP BY sed.cost_center, YEAR(se.posting_date), MONTH(se.posting_date)
		),
		combo AS (
			SELECT cost_center, year, month FROM grv
			UNION
			SELECT cost_center, year, month FROM si
		)
		SELECT
			combo.cost_center AS cost_center,
			DATE_FORMAT(STR_TO_DATE(CONCAT(combo.year, '-', combo.month, '-01'), '%%Y-%%m-%%d'), '%%M %%Y') AS month_year,
			COALESCE(grv.asset_value, 0) AS asset_value,
			COALESCE(grv.material_value, 0) AS material_value,
			COALESCE(grv.service_value, 0) AS service_value,
			COALESCE(si.stock_issue_value, 0) AS stock_issue_value
		FROM combo
		LEFT JOIN grv ON grv.cost_center <=> combo.cost_center AND grv.year = combo.year AND grv.month = combo.month
		LEFT JOIN si ON si.cost_center <=> combo.cost_center AND si.year = combo.year AND si.month = combo.month
		ORDER BY combo.year, combo.month, combo.cost_center
	"""

	return frappe.db.sql(query, {"year": year, "months": months_str}, as_dict=1)
