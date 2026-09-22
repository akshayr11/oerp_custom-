# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Equipment Timesheet.

Daily hours per equipment for the service period, entered as day_1..day_31
on each Equipment Timesheet Detail row. Overtime and the breakdown deduction
are computed here, not left to the user:

    * Status = Working: each day's hours split at the Hiring Contract's own
      "Total Operational Hours" field, used as the normal-hours-per-day cap
      — anything up to it is Normal, anything above is Overtime.
    * Status = Breakdown: the whole row's day total counts as Breakdown
      Hours instead (no Normal/OT split for that equipment this month).
    * Deduction = Breakdown Hours x that row's own rate (the equipment's
      contracted rate, matched from the Hiring Contract's item rows).

This is deliberately not the standard Frappe/ERPNext Timesheet doctype —
that's built around employee time logs against projects/tasks, not daily
per-vehicle hours against a hire contract with its own OT/breakdown rules.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

DAY_FIELDS = [f"day_{d}" for d in range(1, 32)]


class EquipmentTimesheet(Document):
	def validate(self):
		self.set_month_label()
		self.calculate_hours_and_deduction()
		self.validate_rejection_remarks()

	def set_month_label(self):
		if self.service_from_date:
			self.month = getdate(self.service_from_date).strftime("%B %Y")

	def calculate_hours_and_deduction(self):
		threshold = flt(frappe.db.get_value("Hiring Contract", self.hiring_contract, "total_operational_hours"))

		total_normal = total_ot = total_bd = total_deduction = 0

		for row in self.get("details") or []:
			day_total = sum(flt(row.get(f)) for f in DAY_FIELDS)

			if row.status == "Breakdown":
				row.breakdown_hours = day_total
				row.normal_hours = 0
				row.overtime_hours = 0
			else:
				if threshold:
					normal = 0
					overtime = 0
					for f in DAY_FIELDS:
						value = flt(row.get(f))
						normal += min(value, threshold)
						overtime += max(0, value - threshold)
					row.normal_hours = normal
					row.overtime_hours = overtime
				else:
					# No cap configured on the contract — nothing to compare
					# against, so all hours count as normal.
					row.normal_hours = day_total
					row.overtime_hours = 0
				row.breakdown_hours = 0

			row.deduction_amount = flt(row.breakdown_hours) * flt(row.rate)

			total_normal += row.normal_hours
			total_ot += row.overtime_hours
			total_bd += row.breakdown_hours
			total_deduction += row.deduction_amount

		self.total_normal_hours = total_normal
		self.total_overtime_hours = total_ot
		self.total_breakdown_hours = total_bd
		self.total_deduction = total_deduction

	def validate_rejection_remarks(self):
		"""mandatory_depends_on on the field only enforces this in the
		browser — re-checked here so apply_workflow calls, the API and Data
		Import can't reject without a reason either.
		"""
		if self.workflow_state == "Rejected" and not (self.rejection_remarks or "").strip():
			frappe.throw(
				_("Rejection Remarks is mandatory when rejecting an Equipment Timesheet."),
				frappe.MandatoryError,
			)

	def before_cancel(self):
		srv = frappe.db.exists(
			"Service Receipt Voucher", {"equipment_timesheet": self.name, "docstatus": 1}
		)
		if srv:
			frappe.throw(
				_("Cannot cancel: Service Receipt Voucher {0} for this timesheet is already submitted. "
				  "Cancel it first.").format(frappe.bold(srv))
			)
