# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Create a (submitted) Service Purchase Order from an approved Hiring Contract.

Only available once the contract's workflow_state is "Approved" (the single
approval level's final state — see
oerp_custom.oerp_custom.doctype.hiring_contract.setup_workflow).

Item, Qty, UOM and Rate come straight from the contract's own item rows —
nothing is left for the user to review, so unlike the Fleet Hiring Request ->
Hiring Contract step, this one creates the PO fully formed and submits it in
the same call rather than opening an unsaved form.

purchase_type is set to "Service", which drives the PUR-SER naming series via
the existing oerp_custom.overrides.service_naming hooks already wired for
Purchase Order — no naming logic needed here.

VAT: item_tax_template is deliberately left unset on the mapped rows.
AccountsController.set_missing_item_details only fills fields that are still
empty (rate/qty/uom are explicitly mapped, so they're left alone; taxes are
not, so ERPNext's own tax engine looks up each item's tax template and
applies it — this is what "if item has VAT the same must apply" runs through).
"""

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

REFERENCE_FIELD = "custom_reference_hiring_request"


@frappe.whitelist()
def create_purchase_order(source_name):
	source = frappe.get_doc("Hiring Contract", source_name)

	if source.workflow_state != "Approved":
		frappe.throw(_("A Purchase Order can only be created from an Approved Hiring Contract."))

	if not source.fleet_hiring_request:
		frappe.throw(_("This Hiring Contract has no linked Fleet Hiring Request to reference."))

	existing = frappe.db.exists(
		"Purchase Order",
		{REFERENCE_FIELD: source.fleet_hiring_request, "docstatus": ["<", 2]},
	)
	if existing:
		frappe.throw(
			_("A Purchase Order {0} already exists for this Hiring Request.").format(frappe.bold(existing))
		)

	company = _get_company(source)

	def set_missing_values(source, target):
		target.company = company
		target.supplier = source.vendor
		target.purchase_order_type = "Local"
		target.purchase_type = "Service"
		target.custom_from_transport_module = 1
		target.custom_reference_hiring_request = source.fleet_hiring_request
		target.ignore_pricing_rule = 1
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(source_row, target_row, source_parent):
		target_row.stock_qty = target_row.qty
		# reqd on Purchase Order Item; the contract's own start date is the
		# closest thing to a schedule date available on this source chain.
		target_row.schedule_date = source_parent.contract_start_date

	po = get_mapped_doc(
		"Hiring Contract",
		source_name,
		{
			"Hiring Contract": {
				"doctype": "Purchase Order",
				"validation": {"docstatus": ["=", 1]},
			},
			"Hiring Contract Item": {
				"doctype": "Purchase Order Item",
				"field_map": {
					"equipment": "item_code",
					"equipment_name": "item_name",
					"uom": "uom",
					"qty": "qty",
					"rate": "rate",
				},
				"postprocess": update_item,
			},
		},
		None,
		set_missing_values,
	)

	po.insert(ignore_permissions=True)
	po.submit()

	return po.name


def _get_company(source):
	"""Resolve the PO's company from the request's Cost Center.

	Neither Hiring Contract nor Fleet Hiring Request carries its own company
	field — Cost Center already implies one, and this site has more than one
	company, so that's the only reliable source.
	"""
	cost_center = frappe.db.get_value("Fleet Hiring Request", source.fleet_hiring_request, "cost_center")
	company = cost_center and frappe.db.get_value("Cost Center", cost_center, "company")

	if not company:
		frappe.throw(
			_("Could not determine the Company for this Purchase Order from the request's Cost Center.")
		)

	return company
