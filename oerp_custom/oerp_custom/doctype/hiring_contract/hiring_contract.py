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

	def on_update(self):
		self.sync_to_fleet_hiring_request()

	def on_submit(self):
		"""Submitting only happens via the workflow's Approve transition
		(Contract Manager Approval -> Approved is the only docstatus 0 -> 1
		step in this workflow), so this is exactly "when Contract Approved" —
		no separate button, the PO is created and submitted in the same
		transaction as the contract's own approval.
		"""
		from oerp_custom.overrides.hiring_contract import create_purchase_order

		create_purchase_order(self.name)

	def before_cancel(self):
		"""Cancellation rules:

		1. A reason is mandatory (allow_on_submit lets the user fill it in
		   and save before hitting Cancel).
		2. Blocked if the linked Purchase Order has a submitted Purchase
		   Receipt against it — that has to be cancelled first.
		3. Blocked if a submitted Equipment Timesheet references this
		   contract — same reasoning. (Equipment Timesheet has its own
		   before_cancel guarding against an approved Service Receipt
		   Voucher, so the real unwind order is SRV -> Timesheet -> PR ->
		   Contract, each level enforcing the one below it.)
		"""
		if not (self.cancellation_reason or "").strip():
			frappe.throw(
				_("Cancellation Reason is mandatory to cancel a Hiring Contract."), frappe.MandatoryError
			)

		po_name = self.get_linked_purchase_order()
		if po_name and frappe.db.exists("Purchase Receipt Item", {"purchase_order": po_name, "docstatus": 1}):
			frappe.throw(
				_("Cannot cancel: a Purchase Receipt has been created against Purchase Order {0}. "
				  "Cancel the Purchase Receipt first.").format(frappe.bold(po_name))
			)

		timesheet = frappe.db.exists("Equipment Timesheet", {"hiring_contract": self.name, "docstatus": 1})
		if timesheet:
			frappe.throw(
				_("Cannot cancel: Equipment Timesheet {0} against this contract is submitted. "
				  "Cancel it first.").format(frappe.bold(timesheet))
			)

		# The source Fleet Hiring Request stays submitted and keeps its
		# (now historical) hiring_contract link — it shouldn't have to be
		# cancelled itself just to unblock cancelling the contract made from
		# it. Frappe's own check_if_doc_is_linked would otherwise refuse
		# this for exactly that link.
		self.ignore_linked_doctypes = ["Fleet Hiring Request"]

	def on_cancel(self):
		"""No Purchase Receipt exists (checked in before_cancel), so the
		linked PO, if any, is safe to cancel along with the contract.

		Any submitted Contract Extension against this contract is cancelled
		first — Frappe's own referential-integrity check (check_if_doc_is_linked)
		otherwise blocks cancelling a document that a submitted child record
		still links to, regardless of our own before_cancel rules.
		"""
		for name in frappe.get_all(
			"Contract Extension", filters={"hiring_contract": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Contract Extension", name).cancel()

		po_name = self.get_linked_purchase_order()
		if po_name:
			po = frappe.get_doc("Purchase Order", po_name)
			if po.docstatus == 1:
				po.cancel()

	def get_linked_purchase_order(self):
		if not self.fleet_hiring_request:
			return None
		return frappe.db.get_value(
			"Purchase Order",
			{"custom_reference_hiring_request": self.fleet_hiring_request, "docstatus": ["<", 2]},
			"name",
		)

	def sync_to_fleet_hiring_request(self):
		"""Push the contract's main details back onto the source request.

		Explicit frappe.db.set_value rather than relying on fetch_from —
		fetch_from only refreshes when a user touches the form in the
		browser, but this needs to show up immediately, including right
		after on_submit auto-creates the Purchase Order.
		"""
		if not self.fleet_hiring_request:
			return

		frappe.db.set_value(
			"Fleet Hiring Request",
			self.fleet_hiring_request,
			{
				"hiring_contract": self.name,
				"contract_vendor": self.vendor_name,
				"contract_value": self.contract_value,
				"contract_start_date": self.contract_start_date,
				"contract_end_date": self.contract_end_date,
			},
		)

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
