# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HiringContract(Document):
	def validate(self):
		self.calculate_totals()
		self.validate_rejection_remarks()

	def validate_rejection_remarks(self):
		"""Remarks are mandatory on rejection.

		mandatory_depends_on on the field only enforces this in the browser —
		Frappe does not check it server-side (only the static `reqd` flag is
		checked on save). Re-checked here so apply_workflow calls, the API and
		Data Import can't reject without a reason either.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting a Hiring Contract."),
				frappe.MandatoryError,
			)

	def calculate_totals(self):
		"""Row amount = rate * qty; Contract Value = sum of row amounts.

		Recomputed here (not just in the client script) so it's correct
		regardless of how the row got its rate/qty — the browser form, the
		Fleet Hiring Request mapped-doc creation, the API, or Data Import.
		"""
		total = 0
		for row in self.get("items") or []:
			row.amount = flt(row.rate) * flt(row.qty)
			total += row.amount

		self.contract_value = total
