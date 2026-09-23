# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HiringReceipt(Document):
	def validate(self):
		self.calculate_row_amounts()
		self.calculate_totals()
		self.validate_rejection_remarks()

	def calculate_row_amounts(self):
		"""Recomputed on every save, not just when a row is first added —
		Amount/OT Amount/Net Amount/VAT all depend on OT Rate, which the
		user fills in after the row's hours/rate are fetched, so this is
		what keeps them authoritative rather than trusting the client.
		"""
		for row in self.get("timesheets") or []:
			if row.billing_frequency == "Monthly":
				# Normal running is billed at the derived hourly rate;
				# Overtime is billed separately below, at its own rate —
				# so Amount here is Normal Hours only, not Normal + OT.
				row.amount = flt(row.normal_hours) * flt(row.rate)
			else:
				row.amount = flt(row.quantity) * flt(row.rate)

			row.ot_amount = flt(row.overtime_hours) * flt(row.ot_rate)
			row.net_amount = flt(row.amount) + flt(row.ot_amount) - flt(row.deduction_amount)
			row.vat_amount = flt(row.net_amount) * flt(row.vat_rate) / 100 if row.vat_rate else 0

	def calculate_totals(self):
		total_amount = total_ot = total_deduction = total_vat = 0
		for row in self.get("timesheets") or []:
			total_amount += flt(row.amount)
			total_ot += flt(row.ot_amount)
			total_deduction += flt(row.deduction_amount)
			total_vat += flt(row.vat_amount)

		net_amount = total_amount + total_ot - total_deduction

		self.total_amount = total_amount
		self.total_ot_amount = total_ot
		self.total_deduction_amount = total_deduction
		self.net_amount = net_amount
		self.total_vat_amount = total_vat
		self.grand_total = net_amount + total_vat

	def validate_rejection_remarks(self):
		"""mandatory_depends_on on the field only enforces this in the
		browser — re-checked here so apply_workflow calls, the API and Data
		Import can't reject without a reason either.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting a Hiring Receipt."),
				frappe.MandatoryError,
			)

	def on_submit(self):
		"""Submitting only happens via the workflow's Approve transition, so
		this is "Transport approval of the Hiring Receipt followed by
		creation of Purchase Receipt" — in the same transaction, no separate
		button.
		"""
		from oerp_custom.overrides.hiring_receipt import create_purchase_receipt

		create_purchase_receipt(self.name)
