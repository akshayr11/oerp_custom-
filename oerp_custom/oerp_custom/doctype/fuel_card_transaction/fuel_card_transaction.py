# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from oerp_custom.overrides.fuel_card_transaction import get_balance_before, get_fuel_price_for_card


class FuelCardTransaction(Document):
	def validate(self):
		self.fuel_price = get_fuel_price_for_card(self.fuel_card, self.transaction_date)

		balance_before = get_balance_before(self.fuel_card, self.transaction_date, exclude_name=self.name)

		if balance_before <= 0:
			frappe.throw(
				_("{0} has no fuel balance left for this cycle — no further transactions are allowed until it refills.").format(
					frappe.bold(self.fuel_card)
				)
			)

		if flt(self.quantity) > balance_before:
			frappe.throw(
				_("Quantity ({0}) exceeds the {1} balance remaining for this cycle ({2}).").format(
					self.quantity, frappe.bold(self.fuel_card), balance_before
				)
			)

		self.balance_quantity = balance_before - flt(self.quantity)
