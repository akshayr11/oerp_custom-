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

Purely an hours record — no rates, deductions or amounts live here at all;
that's all on the Hiring Receipt this timesheet later feeds into (see
oerp_custom.overrides.hiring_receipt).

An equipment can't appear on two timesheets against the same contract
whose periods overlap — validate_no_duplicate_period() blocks that, so the
same days can't get billed twice.

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
		self.calculate_hours()
		self.validate_no_duplicate_period()
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

	def calculate_hours(self):
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

		total_normal = total_ot = total_bd = 0

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

			total_normal += row.normal_hours
			total_ot += row.overtime_hours
			total_bd += row.breakdown_hours

		self.total_normal_hours = total_normal
		self.total_overtime_hours = total_ot
		self.total_breakdown_hours = total_bd

	def validate_no_duplicate_period(self):
		"""An equipment already billed for a period shouldn't be timesheeted
		again for a period that overlaps it, against the same contract —
		that would double-count (and potentially double-bill, once it goes
		through a Hiring Receipt) the same days.
		"""
		if not (self.hiring_contract and self.service_from_date and self.service_to_date):
			return

		equipment_codes = [row.equipment for row in self.get("details") or [] if row.equipment]
		if not equipment_codes:
			return

		conflict = frappe.db.sql(
			"""
			select et.name, etd.equipment
			from `tabEquipment Timesheet` et
			inner join `tabEquipment Timesheet Detail` etd
				on etd.parent = et.name and etd.parenttype = 'Equipment Timesheet'
			where et.hiring_contract = %(hiring_contract)s
			  and et.name != %(name)s
			  and et.docstatus < 2
			  and etd.equipment in %(equipment_codes)s
			  and et.service_from_date <= %(service_to_date)s
			  and et.service_to_date >= %(service_from_date)s
			limit 1
			""",
			{
				"hiring_contract": self.hiring_contract,
				"name": self.name or "",
				"equipment_codes": equipment_codes,
				"service_to_date": self.service_to_date,
				"service_from_date": self.service_from_date,
			},
			as_dict=True,
		)
		if conflict:
			frappe.throw(
				_(
					"{0} already has a timesheet ({1}) covering an overlapping period against this "
					"contract — adjust the period or remove this equipment."
				).format(frappe.bold(conflict[0].equipment), frappe.bold(conflict[0].name))
			)

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


# ---------------------------------------------------------------------------
# Monthly timesheet upload
#
# Instead of typing day_1..day_31 into the grid, the site fills a sheet
# (Equipment, Equipment Name, Reg. No., Cost Center, Status, 1..31) and
# uploads it. Rows are matched to the contract's equipment, put into the
# Details table and the form is saved, so calculate_hours() works out the
# Normal / OT / BD split exactly as for hand-entered hours.
# ---------------------------------------------------------------------------

TEMPLATE_COLUMNS = ["Equipment", "Equipment Name", "Reg. No.", "Cost Center", "Status"]
HEADER_FIELDS = {
	"equipment": "equipment",
	"equipment code": "equipment",
	"item": "equipment",
	"item code": "equipment",
	"equipment name": "equipment_name",
	"reg. no.": "vehicle_number",
	"reg no": "vehicle_number",
	"reg. no": "vehicle_number",
	"registration no": "vehicle_number",
	"vehicle number": "vehicle_number",
	"vehicle no": "vehicle_number",
	"cost center": "cost_center",
	"cost centre": "cost_center",
	"status": "status",
}


def get_period_days(service_from_date, service_to_date):
	if not (service_from_date and service_to_date):
		return 31
	days = (getdate(service_to_date) - getdate(service_from_date)).days + 1
	return max(1, min(31, days))


@frappe.whitelist()
def download_template(hiring_contract=None, service_from_date=None, service_to_date=None):
	"""Excel sheet to fill: one row per contract equipment, one column per day of the period."""
	from frappe.utils.xlsxutils import make_xlsx

	period_days = get_period_days(service_from_date, service_to_date)
	data = [TEMPLATE_COLUMNS + list(range(1, period_days + 1))]

	if hiring_contract:
		frappe.has_permission("Hiring Contract", "read", hiring_contract, throw=True)
		contract = frappe.get_doc("Hiring Contract", hiring_contract)
		cost_center = contract.get("request_cost_center")
		cost_center = cost_center and frappe.db.get_value("Cost Center", cost_center, "cost_center_name")
		for item in contract.items:
			data.append(
				[item.equipment, item.equipment_name, item.vehicle_number, cost_center or "", "Working"]
				+ [None] * period_days
			)

	month = getdate(service_from_date).strftime("%b %Y") if service_from_date else ""
	frappe.response["filename"] = f"Equipment Timesheet {hiring_contract or ''} {month}".strip() + ".xlsx"
	frappe.response["filecontent"] = make_xlsx(data, "Timesheet").getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def read_timesheet_file(file_url, hiring_contract, service_from_date=None, service_to_date=None):
	"""Rows for the Details table from an uploaded .xlsx / .csv sheet.

	Equipment is matched to the contract's items by code, Equipment Name or
	Reg. No. (the name alone is enough unless two contract rows share it),
	and Cost Center by its name. All problems are reported together.
	"""
	frappe.has_permission("Equipment Timesheet", "write", throw=True)

	sheet = read_sheet(file_url)
	header_idx, columns = find_header(sheet)
	period_days = get_period_days(service_from_date, service_to_date)
	statuses = frappe.get_meta("Equipment Timesheet Detail").get_options("status").split("\n")
	contract = frappe.get_doc("Hiring Contract", hiring_contract)
	default_cost_center = contract.get("request_cost_center")

	rows, errors = [], []
	for line_no, values in enumerate(sheet[header_idx + 1 :], start=header_idx + 2):
		values = dict((field, values[i] if i < len(values) else None) for i, field in columns.items())
		if all(cstr_value(v) == "" for v in values.values()):
			continue

		row_errors = []
		item = match_contract_item(contract, values, row_errors)
		cost_center = match_cost_center(cstr_value(values.get("cost_center")), row_errors) or default_cost_center
		entered_status = cstr_value(values.get("status")) or "Working"
		status = next((s for s in statuses if s and s.lower() == entered_status.lower()), None)
		if not status:
			row_errors.append(
				_("Status {0} is not one of {1}").format(
					frappe.bold(entered_status), ", ".join(filter(None, statuses))
				)
			)

		row = {
			"equipment": item and item.equipment,
			"equipment_name": item and item.equipment_name,
			"vehicle_number": (item and item.vehicle_number) or cstr_value(values.get("vehicle_number")),
			"rate": item and item.rate,
			"cost_center": cost_center,
			"status": status,
		}
		for day in range(1, 32):
			value = values.get(f"day_{day}")
			if cstr_value(value) == "":
				continue
			try:
				hours = flt(value) if isinstance(value, (int, float)) else float(cstr_value(value))
			except ValueError:
				row_errors.append(_("Day {0}: {1} is not a number").format(day, frappe.bold(value)))
				continue
			if hours < 0 or hours > 24:
				row_errors.append(_("Day {0}: {1} hours is not possible").format(day, hours))
			elif hours and day > period_days:
				row_errors.append(_("Day {0} is outside the service period").format(day))
			else:
				row[f"day_{day}"] = hours

		if row_errors:
			errors.append(_("Row {0}: {1}").format(line_no, "; ".join(row_errors)))
		else:
			rows.append(row)

	if errors:
		frappe.throw("<br>".join(errors), title=_("Please correct the sheet and upload again"))
	if not rows:
		frappe.throw(_("No equipment rows found in the sheet."))

	seen = set()
	for row in rows:
		key = (row["equipment"], row["vehicle_number"])
		if key in seen:
			frappe.throw(_("{0} appears more than once in the sheet.").format(frappe.bold(row["equipment_name"] or row["equipment"])))
		seen.add(key)
	return rows


def cstr_value(value):
	return "" if value is None else str(value).strip()


def read_sheet(file_url):
	file = frappe.get_doc("File", {"file_url": file_url})
	extension = (file.file_name or file_url).rsplit(".", 1)[-1].lower()
	if extension == "xlsx":
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		return read_xlsx_file_from_attached_file(fcontent=file.get_content())
	if extension == "csv":
		from frappe.utils.csvutils import read_csv_content

		return read_csv_content(file.get_content())
	frappe.throw(_("Upload the timesheet as an Excel (.xlsx) or CSV file."))


def find_header(sheet):
	"""Index of the header row and {column index: fieldname}; day columns are 1..31 (or dates)."""
	for idx, values in enumerate(sheet[:10]):
		columns = {}
		for i, value in enumerate(values):
			if hasattr(value, "day") and not isinstance(value, str):  # a date used as the column title
				columns[i] = f"day_{value.day}"
				continue
			label = cstr_value(value).lower()
			if label in HEADER_FIELDS:
				columns[i] = HEADER_FIELDS[label]
			else:
				try:
					day = float(label)
				except ValueError:
					continue
				if day.is_integer() and 1 <= day <= 31:
					columns[i] = f"day_{int(day)}"

		fields = set(columns.values())
		if fields & {"equipment", "equipment_name", "vehicle_number"} and any(f.startswith("day_") for f in fields):
			return idx, columns

	frappe.throw(
		_("Header row not found. The sheet needs the columns {0} and one column per day (1, 2, 3 …).").format(
			", ".join(TEMPLATE_COLUMNS)
		)
	)


def match_contract_item(contract, values, errors):
	code = cstr_value(values.get("equipment")).lower()
	name = cstr_value(values.get("equipment_name")).lower()
	reg_no = cstr_value(values.get("vehicle_number")).lower()
	label = cstr_value(values.get("equipment")) or cstr_value(values.get("equipment_name")) or reg_no

	matches = [
		item
		for item in contract.items
		if (code and code in {(item.equipment or "").lower(), (item.equipment_name or "").lower()})
		or (not code and name and name == (item.equipment_name or "").lower())
		or (not code and not name and reg_no and reg_no == (item.vehicle_number or "").lower())
	]
	if len(matches) > 1 and reg_no:
		matches = [item for item in matches if (item.vehicle_number or "").lower() == reg_no] or matches

	if len(matches) == 1:
		return matches[0]
	if not matches:
		errors.append(_("Equipment {0} is not in contract {1}").format(frappe.bold(label), contract.name))
	else:
		errors.append(_("Equipment {0} is on the contract more than once; enter its Reg. No.").format(frappe.bold(label)))


def match_cost_center(value, errors):
	if not value:
		return
	if frappe.db.exists("Cost Center", {"name": value, "is_group": 0}):
		return value
	cost_center = frappe.db.get_value("Cost Center", {"cost_center_name": value, "is_group": 0})
	if not cost_center:
		errors.append(_("Cost Center {0} not found").format(frappe.bold(value)))
	return cost_center
