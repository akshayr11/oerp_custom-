# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Start a Service Receipt Voucher from an approved Equipment Timesheet.

A voucher can span several timesheets (oerp_custom.overrides.service_receipt_voucher),
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

from oerp_custom.overrides.service_receipt_voucher import get_row_details


@frappe.whitelist()
def create_service_receipt_voucher(source_name):
	source = frappe.get_doc("Equipment Timesheet", source_name)

	if source.docstatus != 1 or source.workflow_state != "Approved":
		frappe.throw(_("A Service Receipt Voucher can only be started from an Approved Equipment Timesheet."))

	srv = frappe.new_doc("Service Receipt Voucher")
	srv.hiring_contract = source.hiring_contract
	date = getdate(source.service_from_date)
	srv.service_month = date.strftime("%B")
	srv.service_year = date.year

	for row in source.details:
		details = get_row_details(source.hiring_contract, source_name, row.equipment)
		srv.append("timesheets", {"timesheet": source_name, "equipment": row.equipment, **details})

	return srv
