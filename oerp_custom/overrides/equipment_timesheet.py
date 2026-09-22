# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Create a Service Receipt Voucher from an approved Equipment Timesheet.

Unlike the Hiring Contract -> Purchase Order step, this is a deliberate
manual action ("Once approved user creates a service receipt voucher") —
opens an unsaved form for the user to review, not an auto-submit.
"""

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc


@frappe.whitelist()
def create_service_receipt_voucher(source_name, target_doc=None):
	source = frappe.get_doc("Equipment Timesheet", source_name)

	if source.docstatus != 1 or source.workflow_state != "Approved":
		frappe.throw(_("A Service Receipt Voucher can only be created from an Approved Equipment Timesheet."))

	existing = frappe.db.exists(
		"Service Receipt Voucher",
		{"equipment_timesheet": source_name, "docstatus": ["<", 2]},
	)
	if existing:
		frappe.throw(
			_("Service Receipt Voucher {0} already exists for this Equipment Timesheet.").format(
				frappe.bold(existing)
			)
		)

	return get_mapped_doc(
		"Equipment Timesheet",
		source_name,
		{
			"Equipment Timesheet": {
				"doctype": "Service Receipt Voucher",
				"field_map": {"name": "equipment_timesheet"},
				"validation": {"docstatus": ["=", 1]},
			},
		},
		target_doc,
	)
