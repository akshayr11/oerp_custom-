# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FuelCardPrices(Document):
	def validate(self):
		if self.current_status != "Active":
			return

		existing = frappe.db.exists(
			"Fuel Card Prices",
			{
				"fuel_type": self.fuel_type,
				"month": self.month,
				"year": self.year,
				"cost_center": self.cost_center,
				"current_status": "Active",
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("{0} is already the active price for {1} in {2} {3} at {4}.").format(
					frappe.bold(existing),
					frappe.bold(self.fuel_type),
					self.month,
					self.year,
					frappe.bold(self.cost_center),
				)
			)
