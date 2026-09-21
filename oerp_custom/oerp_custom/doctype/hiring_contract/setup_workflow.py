# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Hiring Contract approval workflow — source of truth for its design.

The Workflow this creates is exported as a fixture
(oerp_custom/fixtures/workflow.json alongside the Fleet Hiring Request one),
so a plain `bench migrate` already recreates it on any site — this script
does not need to be run there. It exists so the workflow's shape can be
rebuilt or changed in one place: edit STATES/TRANSITIONS below, rerun this,
then `bench export-fixtures` to refresh the JSON.

    bench --site <site> execute oerp_custom.oerp_custom.doctype.hiring_contract.setup_workflow.run

One approval level, reusing the Contract Manager role and the Draft /
Contract Manager Approval / Approved / Rejected Workflow States already
created for the Fleet Hiring Request workflow — no new roles or states
needed here. Only the final Approve submits the document (docstatus 0 -> 1);
Rejected stays docstatus 0.
"""

import frappe

DOCTYPE = "Hiring Contract"

STATES = [
	# state, doc_status, allow_edit role
	("Draft", "0", "Transport Officer"),
	("Contract Manager Approval", "0", "Contract Manager"),
	("Approved", "1", ""),
	("Rejected", "0", ""),
]

TRANSITIONS = [
	# state, action, next_state, allowed role
	("Draft", "Review", "Contract Manager Approval", "Transport Officer"),
	("Contract Manager Approval", "Approve", "Approved", "Contract Manager"),
	("Contract Manager Approval", "Reject", "Rejected", "Contract Manager"),
]


def run():
	create_workflow()
	frappe.db.commit()
	print("Hiring Contract workflow ready.")


def create_workflow():
	if frappe.db.exists("Workflow", DOCTYPE):
		frappe.delete_doc("Workflow", DOCTYPE, ignore_permissions=True, force=True)

	doc = frappe.new_doc("Workflow")
	doc.workflow_name = DOCTYPE
	doc.document_type = DOCTYPE
	doc.workflow_state_field = "workflow_state"
	doc.is_active = 1
	doc.send_email_alert = 0

	for state, doc_status, allow_edit in STATES:
		doc.append(
			"states",
			{
				"state": state,
				"doc_status": doc_status,
				"allow_edit": allow_edit or "System Manager",
			},
		)

	for state, action, next_state, allowed in TRANSITIONS:
		doc.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": allowed,
			},
		)

	doc.insert(ignore_permissions=True)
