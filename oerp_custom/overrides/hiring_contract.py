# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Create a (submitted) Service Purchase Order from an approved Hiring Contract.

Called automatically from HiringContract.on_submit — submitting only
happens via the workflow's Approve transition (the single approval level's
final state, see
oerp_custom.oerp_custom.doctype.hiring_contract.setup_workflow), so this
runs the moment the contract is approved, in the same transaction. No
separate button or manual step.

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
from frappe.utils import getdate, today

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
		# get_mapped_doc copies over any field the source and target share
		# by name — Hiring Contract and Purchase Order both have their own
		# separate workflow_state, so without this a fresh PO would start
		# pre-set to "Approved" (the contract's own final state), which its
		# own workflow then rejects as an invalid transition from a
		# document that's supposed to still be new/Draft.
		target.workflow_state = None
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
		# reqd on Purchase Order Item, and cannot be before the PO's own
		# transaction_date (defaults to today, since we never set it
		# explicitly). The contract's start date is often in the past by
		# the time the contract is actually approved — a hire contract
		# commonly gets approved after its period has already begun — so
		# fall back to today whenever that would violate that rule.
		target_row.schedule_date = max(getdate(source_parent.contract_start_date), getdate(today()))

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

	# Explicit frappe.db.set_value, not self.xxx = — this runs from
	# on_submit, after the contract's own submit-save already wrote its
	# row; setting a plain attribute here wouldn't get persisted.
	frappe.db.set_value("Hiring Contract", source_name, "purchase_order", po.name)

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
