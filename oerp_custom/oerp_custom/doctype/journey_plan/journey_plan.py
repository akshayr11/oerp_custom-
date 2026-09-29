# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class JourneyPlan(Document):
	def validate(self):
		self.no_of_passengers = len(self.get("passengers") or [])
		self.validate_checklist_reasons()
		self.validate_rejection_remarks()
		self.validate_closure_fields()

	def before_update_after_submit(self):
		"""The Execute transition edits an already-submitted document, so
		Frappe runs this hook instead of validate() (see run_before_save_methods
		in frappe/model/document.py — validate() is only called for the
		"save"/"submit" actions, never for "update_after_submit"). Without this,
		the mandatory closure check below would silently never run.
		"""
		self.validate_closure_fields()

	def validate_checklist_reasons(self):
		"""mandatory_depends_on on these fields only enforces this in the
		browser — re-checked here so apply_workflow calls, the API and Data
		Import can't skip a reason either.
		"""
		if self.can_be_combined_with_another_journey == "No" and not (self.reason_if_not_combined or "").strip():
			frappe.throw(
				_("Reason If Not Combined is mandatory when the journey cannot be combined with another."),
				frappe.MandatoryError,
			)
		if self.night_driving == "Yes" and not (self.reason_for_night_driving or "").strip():
			frappe.throw(
				_("Reason for Night Driving is mandatory when Night Driving is Yes."),
				frappe.MandatoryError,
			)

	def validate_rejection_remarks(self):
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting a Journey Plan."),
				frappe.MandatoryError,
			)

	def validate_closure_fields(self):
		"""mandatory_depends_on on these fields only enforces this in the
		browser — re-checked here so apply_workflow calls, the API and Data
		Import can't skip closure either.
		"""
		if self.workflow_state != "Executed":
			return
		if not self.closure_meter_reading:
			frappe.throw(
				_("Current Meter Reading is mandatory when executing a Journey Plan."),
				frappe.MandatoryError,
			)
		if not (self.specific_journey_details or "").strip():
			frappe.throw(
				_("Specific Journey Details is mandatory when executing a Journey Plan."),
				frappe.MandatoryError,
			)
