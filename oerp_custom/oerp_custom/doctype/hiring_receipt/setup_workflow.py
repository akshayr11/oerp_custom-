# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Hiring Receipt approval workflow — source of truth for its design.

Exported as a fixture (oerp_custom/fixtures/workflow.json), so a plain
`bench migrate` already recreates it on any site — this script does not
need to be run there. Rerun after editing STATES/TRANSITIONS, then
`bench export-fixtures`.

    bench --site <site> execute oerp_custom.oerp_custom.doctype.hiring_receipt.setup_workflow.run

One approval level, reusing the "Transport Officer Final Approval" Workflow
State already created for the Fleet Hiring Request workflow (state name
only — not a role), so no new state is needed. Every transition's "allowed"
and "allow_edit" is System Manager: no roles/permissions spec was given, so
nothing is gated by an invented role. Restrict this to real roles once you
have them. Only the final Approve submits the document (docstatus 0 -> 1),
which triggers Purchase Receipt creation via on_submit.
"""

import frappe

DOCTYPE = "Hiring Receipt"

STATES = [
	("Draft", "0"),
	("Transport Officer Final Approval", "0"),
	("Approved", "1"),
	("Rejected", "0"),
]

TRANSITIONS = [
	("Draft", "Review", "Transport Officer Final Approval"),
	("Transport Officer Final Approval", "Approve", "Approved"),
	("Transport Officer Final Approval", "Reject", "Rejected"),
]


def run():
	create_workflow()
	frappe.db.commit()
	print("Hiring Receipt workflow ready.")


def create_workflow():
	if frappe.db.exists("Workflow", DOCTYPE):
		frappe.delete_doc("Workflow", DOCTYPE, ignore_permissions=True, force=True)

	doc = frappe.new_doc("Workflow")
	doc.workflow_name = DOCTYPE
	doc.document_type = DOCTYPE
	doc.workflow_state_field = "workflow_state"
	doc.is_active = 1
	doc.send_email_alert = 0

	for state, doc_status in STATES:
		doc.append("states", {"state": state, "doc_status": doc_status, "allow_edit": "System Manager"})

	for state, action, next_state in TRANSITIONS:
		doc.append(
			"transitions",
			{"state": state, "action": action, "next_state": next_state, "allowed": "System Manager"},
		)

	doc.insert(ignore_permissions=True)
