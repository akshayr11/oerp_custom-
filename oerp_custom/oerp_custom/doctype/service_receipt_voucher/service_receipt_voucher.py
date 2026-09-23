# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ServiceReceiptVoucher(Document):
	def validate(self):
		self.calculate_totals()
		self.validate_rejection_remarks()

	def calculate_totals(self):
		total_amount = total_vat = 0
		for row in self.get("timesheets") or []:
			total_amount += flt(row.amount)
			total_vat += flt(row.vat_amount)

		self.total_amount = total_amount
		self.total_vat_amount = total_vat
		self.grand_total = total_amount + total_vat

	def validate_rejection_remarks(self):
		"""mandatory_depends_on on the field only enforces this in the
		browser — re-checked here so apply_workflow calls, the API and Data
		Import can't reject without a reason either.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting a Service Receipt Voucher."),
				frappe.MandatoryError,
			)

	def on_submit(self):
		"""Submitting only happens via the workflow's Approve transition, so
		this is "Transport approval of service receipt voucher followed by
		creation of Purchase receipt" — in the same transaction, no separate
		button.
		"""
		from oerp_custom.overrides.service_receipt_voucher import create_purchase_receipt

		create_purchase_receipt(self.name)
