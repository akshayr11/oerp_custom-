# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Equipment Timesheet.

Daily hours per equipment for the service period, entered as day_1..day_31
on each Equipment Timesheet Detail row. Per row, keyed off Status:

    * Working: each day's hours are split at the Hiring Contract's own
      "Total Operational Hours" field (the normal-hours-per-day cap) —
      anything up to it is Normal, anything above is Overtime, both summed
      across the period. On a Monthly-billed contract item specifically,
      the shortfall below the cap on days that fall short is *also* summed
      and recorded as Breakdown Hours (this is what lets a single month
      carry both Overtime and Breakdown at once — see the Service Receipt
      Voucher's hourly billing model for Monthly items). Non-Monthly
      contract items keep Breakdown Hours at 0 in Working status, same as
      before — nothing here changes for them.
    * Breakdown: the whole row's day total counts as Breakdown Hours
      instead (no Normal/OT split for that equipment this month).
    * Idle / Overtime / Off / De-hired: not billable at all — Normal, OT
      and Breakdown Hours all come out to 0 regardless of what's entered
      in the day fields, since none of these represents ordinary billable
      running time.

    * Deduction Amount, Extra Charges and OT Amount are entered by the user
      directly — not derived from hours or anything else, so someone can
      apply a negotiated/adjusted figure rather than a strict formula.
    * Net Rate = Rate - Deduction Amount + Extra Charges. Computed here.

This is deliberately not the standard Frappe/ERPNext Timesheet doctype —
that's built around employee time logs against projects/tasks, not daily
per-vehicle hours against a hire contract with its own OT/breakdown rules.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

DAY_FIELDS = [f"day_{d}" for d in range(1, 32)]
NOT_BILLABLE_STATUSES = {"Idle", "Overtime", "Off", "De-hired"}


class EquipmentTimesheet(Document):
	def validate(self):
		self.set_month_label()
		self.calculate_hours_and_deduction()
		self.validate_rejection_remarks()

	def set_month_label(self):
		if self.service_from_date:
			self.month = getdate(self.service_from_date).strftime("%B %Y")

	def get_active_day_fields(self):
		"""Bound to the timesheet's own period length — a 30-day period's
		day_31 field doesn't represent a real day, so it must never be
		treated as "0 hours logged, so a full threshold's worth of
		breakdown deficit" the way an actually-worked-but-short day would.
		"""
		if not (self.service_from_date and self.service_to_date):
			return DAY_FIELDS
		period_days = (getdate(self.service_to_date) - getdate(self.service_from_date)).days + 1
		period_days = max(1, min(31, period_days))
		return DAY_FIELDS[:period_days]

	def calculate_hours_and_deduction(self):
		threshold = flt(frappe.db.get_value("Hiring Contract", self.hiring_contract, "total_operational_hours"))
		active_day_fields = self.get_active_day_fields()
		monthly_equipment = set(
			frappe.get_all(
				"Hiring Contract Item",
				filters={
					"parent": self.hiring_contract,
					"parenttype": "Hiring Contract",
					"frequency": "Monthly",
				},
				pluck="equipment",
			)
		)

		total_normal = total_ot = total_bd = total_deduction = total_extra = total_ot_amount = 0

		for row in self.get("details") or []:
			day_total = sum(flt(row.get(f)) for f in active_day_fields)

			if row.status in NOT_BILLABLE_STATUSES:
				row.normal_hours = 0
				row.overtime_hours = 0
				row.breakdown_hours = 0
			elif row.status == "Breakdown":
				row.breakdown_hours = day_total
				row.normal_hours = 0
				row.overtime_hours = 0
			else:
				if threshold:
					normal = overtime = deficit = 0
					for f in active_day_fields:
						value = flt(row.get(f))
						normal += min(value, threshold)
						overtime += max(0, value - threshold)
						deficit += max(0, threshold - value)
					row.normal_hours = normal
					row.overtime_hours = overtime
					row.breakdown_hours = deficit if row.equipment in monthly_equipment else 0
				else:
					# No cap configured on the contract — nothing to compare
					# against, so all hours count as normal.
					row.normal_hours = day_total
					row.overtime_hours = 0
					row.breakdown_hours = 0

			# Deduction Amount, Extra Charges and OT Amount are the user's
			# own entries — not derived here. Net Rate is the only thing
			# computed from them.
			row.net_rate = flt(row.rate) - flt(row.deduction_amount) + flt(row.extra_charges)

			total_normal += row.normal_hours
			total_ot += row.overtime_hours
			total_bd += row.breakdown_hours
			total_deduction += flt(row.deduction_amount)
			total_extra += flt(row.extra_charges)
			total_ot_amount += flt(row.ot_amount)

		self.total_normal_hours = total_normal
		self.total_overtime_hours = total_ot
		self.total_breakdown_hours = total_bd
		self.total_deduction = total_deduction
		self.total_extra_charges = total_extra
		self.total_ot_amount = total_ot_amount

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
		"""A Hiring Receipt links to timesheets via its own child table (a
		voucher can span several timesheets), not a single Link field —
		check that table instead, filtered to rows still belonging to a
		submitted voucher.
		"""
		row = frappe.db.get_value(
			"Hiring Receipt Timesheet",
			{"timesheet": self.name, "docstatus": 1},
			"parent",
		)
		if row:
			frappe.throw(
				_("Cannot cancel: Hiring Receipt {0} against this timesheet is already submitted. "
				  "Cancel it first.").format(frappe.bold(row))
			)
