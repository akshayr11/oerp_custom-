# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Start a Hiring Receipt from an approved Equipment Timesheet.

A voucher can span several timesheets (oerp_custom.overrides.hiring_receipt),
so this doesn't map the timesheet directly onto the voucher the way the
Hiring Contract -> Purchase Order step maps a contract onto a PO. It just
opens a new, unsaved voucher with Contract and Service Month/Year pre-filled
from this timesheet, and this timesheet's own equipment rows added as a
starting point — the user can add more timesheets for the same
contract/month from there, or remove rows, before submitting.
"""

import frappe
from frappe import _
from frappe.utils import getdate

from oerp_custom.overrides.hiring_receipt import get_row_details


@frappe.whitelist()
def create_hiring_receipt(source_name):
	source = frappe.get_doc("Equipment Timesheet", source_name)

	if source.docstatus != 1 or source.workflow_state != "Approved":
		frappe.throw(_("A Hiring Receipt can only be started from an Approved Equipment Timesheet."))

	hr = frappe.new_doc("Hiring Receipt")
	hr.hiring_contract = source.hiring_contract
	date = getdate(source.service_from_date)
	hr.service_month = date.strftime("%B")
	hr.service_year = date.year

	for row in source.details:
		details = get_row_details(source.hiring_contract, source_name, row.equipment)
		hr.append("timesheets", {"timesheet": source_name, "equipment": row.equipment, **details})

	return hr
