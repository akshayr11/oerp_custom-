# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Equipment Certificate: expiry-date calculation, status, and the daily
expiry-notification job (see hooks.py's scheduler_events -> "daily").

Expiry Date = Issue Date + Certificate Type's own Duration, in units of its
Frequency (Weekly/Monthly/Yearly) — only computed when Expiry Date is still
blank, so a manually-entered/overridden date is never clobbered.

Status is a straight function of today vs. Expiry Date — Expired if past,
Expiring Soon inside the advance-warning window, Active otherwise. Recomputed
on every Equipment Certificate save, and again daily by the notification job
(so a certificate nobody has opened in months still shows the right status).

No roles exist for this app, so the daily job notifies System Manager users
directly (Notification Log + a single digest email each) rather than a
Transport-specific role — reassign this once real roles are defined.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, add_years, cint, getdate, today

ADVANCE_WARNING_DAYS = 30


def compute_expiry_date(certificate_type, issue_date):
	if not (certificate_type and issue_date):
		return None

	master = frappe.db.get_value(
		"Equipment Certificate Master", certificate_type, ["frequency", "duration"], as_dict=True
	)
	if not master:
		return None

	duration = cint(master.duration) or 1
	issue = getdate(issue_date)

	if master.frequency == "Weekly":
		return add_days(issue, 7 * duration)
	if master.frequency == "Monthly":
		return add_months(issue, duration)
	if master.frequency == "Yearly":
		return add_years(issue, duration)
	return None


@frappe.whitelist()
def get_expiry_date(certificate_type, issue_date):
	return compute_expiry_date(certificate_type, issue_date)


def compute_status(expiry_date):
	if not expiry_date:
		return "Active"

	days_left = (getdate(expiry_date) - getdate(today())).days
	if days_left < 0:
		return "Expired"
	if days_left <= ADVANCE_WARNING_DAYS:
		return "Expiring Soon"
	return "Active"


def notify_expiring_certificates():
	"""Daily scheduled job. Refreshes every live Equipment Certificate's
	Status, then sends one digest Notification Log + email per System
	Manager user listing everything Expiring Soon or Expired. Runs every
	day regardless of whether yesterday's notification was seen, so a
	lapsed certificate keeps surfacing until it's actually renewed.
	"""
	rows = frappe.get_all(
		"Equipment Certificate",
		filters={"docstatus": ["<", 2]},
		fields=["name", "equipment_name", "certificate_type", "expiry_date", "status"],
	)

	due = []
	for row in rows:
		status = compute_status(row.expiry_date)
		if status != row.status:
			frappe.db.set_value("Equipment Certificate", row.name, "status", status, update_modified=False)
		if status in ("Expiring Soon", "Expired"):
			due.append((row, status))

	# Committed on its own, independent of whether notifying anyone below
	# succeeds — Status staying accurate shouldn't depend on mail working.
	frappe.db.commit()

	if not due:
		return

	recipients = _get_system_manager_users()
	for user in recipients:
		_notify_user(user, due)


def _get_system_manager_users():
	users = frappe.get_all(
		"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
	)
	return [
		u
		for u in users
		if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled")
	]


def _notify_user(user, due):
	"""Notification Log and email are independent channels — the in-app one
	needs nothing but the database, so a broken/unconfigured outgoing Email
	Account (or any other mail failure) must never take it down too, or
	silently stop the rest of the recipients from being notified on top of
	that. Each channel gets its own try/except and its own commit.
	"""
	lines = [
		_("{0} ({1}) for {2} — {3} on {4}").format(
			row.name,
			row.certificate_type,
			row.equipment_name or row.name,
			_("expires") if status == "Expiring Soon" else _("expired"),
			frappe.utils.formatdate(row.expiry_date),
		)
		for row, status in due
	]
	subject = _("{0} equipment certificate(s) need attention").format(len(due))
	message = "<br>".join(lines)

	try:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"subject": subject,
				"type": "Alert",
				"document_type": "Equipment Certificate",
				"document_name": due[0][0].name,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Equipment Certificate Notification Log failed for {user}")

	email = frappe.db.get_value("User", user, "email")
	if not email:
		return
	try:
		frappe.sendmail(recipients=[email], subject=subject, message=message)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Equipment Certificate email notification failed for {user}")
