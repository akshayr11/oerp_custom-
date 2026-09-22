# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceReceiptVoucher(Document):
	def validate(self):
		self.validate_timesheet_approved()
		self.validate_no_duplicate()

	def validate_timesheet_approved(self):
		if not self.equipment_timesheet:
			return

		workflow_state, docstatus = frappe.db.get_value(
			"Equipment Timesheet", self.equipment_timesheet, ["workflow_state", "docstatus"]
		)
		if docstatus != 1 or workflow_state != "Approved":
			frappe.throw(
				_("A Service Receipt Voucher can only be raised against an Approved Equipment Timesheet.")
			)

	def validate_no_duplicate(self):
		existing = frappe.db.exists(
			"Service Receipt Voucher",
			{
				"equipment_timesheet": self.equipment_timesheet,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("Service Receipt Voucher {0} already exists for this Equipment Timesheet.").format(
					frappe.bold(existing)
				)
			)
