# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ContractExtension(Document):
	def validate(self):
		self.validate_rejection_remarks()

	def validate_rejection_remarks(self):
		"""Remarks are mandatory on rejection.

		mandatory_depends_on on the field only enforces this in the browser —
		Frappe does not check it server-side. Re-checked here so
		apply_workflow calls, the API and Data Import can't reject without a
		reason either.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting a Contract Extension."),
				frappe.MandatoryError,
			)

	def on_submit(self):
		"""Submitting only happens via the workflow's Approve transition, so
		this is "upon approval of the extension" — update the contract's
		expiry date in the same transaction as this document's own approval.
		"""
		contract = frappe.get_doc("Hiring Contract", self.hiring_contract)
		contract.db_set("contract_end_date", self.new_expiry_date)
		contract.sync_to_fleet_hiring_request()
