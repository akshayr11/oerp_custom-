# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from oerp_custom.overrides.equipment_certificate import compute_expiry_date, compute_status


class EquipmentCertificateRenewal(Document):
	def validate(self):
		self.validate_equipment_matches()
		for row in self.get("renewals") or []:
			if not row.new_expiry_date:
				row.new_expiry_date = compute_expiry_date(row.certificate_type, row.new_issue_date)

			if row.new_issue_date and row.new_expiry_date and getdate(row.new_expiry_date) < getdate(row.new_issue_date):
				frappe.throw(
					_("Row {0}: New Expiry Date cannot be before New Issue Date.").format(row.idx)
				)

	def validate_equipment_matches(self):
		"""Every certificate being renewed here has to actually belong to
		the header's own Equipment — otherwise this one renewal record
		would be quietly updating a different piece of equipment's
		certificate.
		"""
		for row in self.get("renewals") or []:
			cert_equipment = frappe.db.get_value("Equipment Certificate", row.equipment_certificate, "equipment")
			if cert_equipment != self.equipment:
				frappe.throw(
					_("Row {0}: {1} belongs to {2}, not {3}.").format(
						row.idx, frappe.bold(row.equipment_certificate), frappe.bold(cert_equipment), frappe.bold(self.equipment)
					)
				)

	def on_submit(self):
		"""Submitting is the renewal event itself — no separate approval
		step, matching this feature's own scope (a compliance record, not a
		commercial transaction). Push each row's new dates onto its own
		Equipment Certificate, in the same transaction — one renewal
		document can cover several certificates for the one equipment.
		"""
		for row in self.get("renewals") or []:
			cert = frappe.get_doc("Equipment Certificate", row.equipment_certificate)
			cert.db_set("issue_date", row.new_issue_date)
			cert.db_set("expiry_date", row.new_expiry_date)
			if row.certificate_number:
				cert.db_set("certificate_number", row.certificate_number)
			cert.db_set("status", compute_status(row.new_expiry_date))

	def on_cancel(self):
		"""The certificates' current dates stay whatever this renewal set
		them to — cancelling the renewal record doesn't revert them, since
		an equally-valid later renewal may already have moved them on
		again. This just removes the (mistaken) record from the history.
		"""
		pass
