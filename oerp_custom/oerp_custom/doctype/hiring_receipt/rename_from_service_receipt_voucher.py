# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""One-time rename: "Service Receipt Voucher" -> "Hiring Receipt".

Run this ONCE on each site that already has the old doctype (i.e.
production, or any site that pulled the Service Receipt Voucher feature
before this rename), and run it BEFORE `bench migrate` — not after. If
`bench migrate` runs first, it'll see this app's files already declaring
"Hiring Receipt" with no "Service Receipt Voucher" doctype/JSON left
anywhere, and create a brand new empty "Hiring Receipt" table alongside
the untouched old one, instead of turning the old one into the new one.

    git pull origin main
    bench --site <site> execute oerp_custom.oerp_custom.doctype.hiring_receipt.rename_from_service_receipt_voucher.run
    bench --site <site> migrate

Safe to run even if "Service Receipt Voucher" doesn't exist on this site
(e.g. a fresh site that never had the old name) — it just does nothing.
Uses frappe.rename_doc, which renames the underlying table and cascades
the rename through every Link/Table field across the site that points at
it (Workflow.document_type among them), so any real Service Receipt
Voucher records already created stay intact under their new name.
"""

import frappe


def run():
	if not frappe.db.exists("DocType", "Service Receipt Voucher"):
		print("Nothing to rename — 'Service Receipt Voucher' doesn't exist on this site.")
		return

	# Child table first: renaming it updates the parent doctype's own
	# Table field (options="Service Receipt Voucher Timesheet") to the
	# new name automatically, regardless of which order these two run in
	# relative to each other — but child-first mirrors how the doctypes
	# actually depend on each other.
	if frappe.db.exists("DocType", "Service Receipt Voucher Timesheet"):
		frappe.rename_doc("DocType", "Service Receipt Voucher Timesheet", "Hiring Receipt Timesheet", force=True)

	frappe.rename_doc("DocType", "Service Receipt Voucher", "Hiring Receipt", force=True)

	# The Workflow's own document_type field gets updated by the DocType
	# rename above (it's a Link field), but the Workflow record's own name
	# doesn't — rename that separately.
	if frappe.db.exists("Workflow", "Service Receipt Voucher"):
		frappe.rename_doc("Workflow", "Service Receipt Voucher", "Hiring Receipt", force=True)

	# A stray Property Setter (seen locally, origin unclear — possibly
	# left over from an earlier Desk UI edit) can pin naming_series.options
	# to the old "ALG/T-L/SRV/..." series even after the DocType's own
	# JSON says "ALG/T-L/HREC/...", since Property Setters take precedence
	# over the base field definition. Harmless to delete if absent.
	if frappe.db.exists("Property Setter", "Service Receipt Voucher-naming_series-options"):
		frappe.delete_doc(
			"Property Setter", "Service Receipt Voucher-naming_series-options", ignore_permissions=True
		)

	frappe.db.commit()
	frappe.clear_cache()
	print("Renamed 'Service Receipt Voucher' -> 'Hiring Receipt'. Now run: bench migrate")
