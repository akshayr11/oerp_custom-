# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Contract Extension approval workflow — source of truth for its design.

Exported as a fixture (oerp_custom/fixtures/workflow.json), so a plain
`bench migrate` already recreates it on any site — this script does not
need to be run there. Rerun after editing STATES/TRANSITIONS, then
`bench export-fixtures`.

    bench --site <site> execute oerp_custom.oerp_custom.doctype.contract_extension.setup_workflow.run

One approval level, reusing the Draft / Contract Manager Approval / Approved
/ Rejected Workflow States already created for the Fleet Hiring Request /
Hiring Contract workflows (state names only — not roles). Every transition's
"allowed" and "allow_edit" is System Manager: no roles/permissions spec was
given, so nothing is gated by an invented role. Restrict this to real roles
once you have them. Only the final Approve submits the document (docstatus
0 -> 1), which triggers ContractExtension.on_submit to update the linked
contract's expiry date.
"""

import frappe

DOCTYPE = "Contract Extension"

STATES = [
	("Draft", "0"),
	("Contract Manager Approval", "0"),
	("Approved", "1"),
	("Rejected", "0"),
]

TRANSITIONS = [
	("Draft", "Review", "Contract Manager Approval"),
	("Contract Manager Approval", "Approve", "Approved"),
	("Contract Manager Approval", "Reject", "Rejected"),
]


def run():
	create_workflow()
	frappe.db.commit()
	print("Contract Extension workflow ready.")


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
