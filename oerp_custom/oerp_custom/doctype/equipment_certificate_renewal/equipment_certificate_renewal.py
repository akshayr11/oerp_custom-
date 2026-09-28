# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from oerp_custom.overrides.equipment_certificate import compute_expiry_date, compute_status


class EquipmentCertificateRenewal(Document):
	def validate(self):
		if not self.new_expiry_date:
			self.new_expiry_date = compute_expiry_date(self.certificate_type, self.new_issue_date)

		if self.new_issue_date and self.new_expiry_date and getdate(self.new_expiry_date) < getdate(self.new_issue_date):
			frappe.throw(_("New Expiry Date cannot be before New Issue Date."))

	def on_submit(self):
		"""Submitting is the renewal event itself — no separate approval
		step, matching this feature's own scope (a compliance record, not a
		commercial transaction). Push the new dates onto the Equipment
		Certificate in the same transaction.
		"""
		cert = frappe.get_doc("Equipment Certificate", self.equipment_certificate)
		cert.db_set("issue_date", self.new_issue_date)
		cert.db_set("expiry_date", self.new_expiry_date)
		if self.certificate_number:
			cert.db_set("certificate_number", self.certificate_number)
		cert.db_set("status", compute_status(self.new_expiry_date))

	def on_cancel(self):
		"""The certificate's current dates stay whatever this renewal set
		them to — cancelling the renewal record doesn't revert them, since
		an equally-valid later renewal may already have moved them on
		again. This just removes the (mistaken) record from the history.
		"""
		pass
