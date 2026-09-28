# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from oerp_custom.overrides.equipment_certificate import compute_expiry_date, compute_status


class EquipmentCertificate(Document):
	def validate(self):
		if not self.expiry_date:
			self.expiry_date = compute_expiry_date(self.certificate_type, self.issue_date)
		self.status = compute_status(self.expiry_date)
