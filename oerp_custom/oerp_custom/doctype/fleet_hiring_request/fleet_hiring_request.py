# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FleetHiringRequest(Document):
	def validate(self):
		self.validate_rejection_remarks()

	def validate_rejection_remarks(self):
		"""Remarks are mandatory on rejection at every approval stage.

		mandatory_depends_on on the field only enforces this in the browser —
		Frappe does not check it server-side (only the static `reqd` flag is
		checked on save). Anything reaching this doc outside the form
		(apply_workflow calls, the API, Data Import) would otherwise be able
		to reject without a reason, so it is re-checked here.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting a Fleet Hiring Request."),
				frappe.MandatoryError,
			)
