# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Journey Plan approval workflow — source of truth for its design.

Exported as a fixture (oerp_custom/fixtures/workflow.json), so a plain
`bench migrate` already recreates it on any site — this script does not
need to be run there. Rerun after editing STATES/TRANSITIONS, then
`bench export-fixtures`.

    bench --site <site> execute oerp_custom.oerp_custom.doctype.journey_plan.setup_workflow.run

One approval level, reusing the "Transport Officer Final Approval" Workflow
State already created for the Fleet Hiring Request workflow (state name
only — not a role) — "Executed" is new, so it's created as its own
Workflow State record here first (a State is a Link field, not free text;
"Draft"/"Approved"/"Rejected" only worked without this because they ship
as Frappe's own standard states). Every transition's "allowed" and
"allow_edit" is System Manager: no roles/permissions spec was given, so
nothing is gated by an invented role. Restrict this to real roles once you
have them. Approve submits the document (docstatus 0 -> 1); Execute is a
later, separate action on that same already-submitted document (docstatus
stays 1 — Executed is not a fresh submission) marking the journey as
actually undertaken, with its own mandatory closure fields (see
JourneyPlan.validate_closure_fields).
"""

import frappe

DOCTYPE = "Journey Plan"

NEW_STATES = ["Executed"]
NEW_ACTIONS = ["Execute"]

STATES = [
	("Draft", "0"),
	("Transport Officer Final Approval", "0"),
	("Approved", "1"),
	("Executed", "1"),
	("Rejected", "0"),
]

TRANSITIONS = [
	("Draft", "Review", "Transport Officer Final Approval"),
	("Transport Officer Final Approval", "Approve", "Approved"),
	("Transport Officer Final Approval", "Reject", "Rejected"),
	("Approved", "Execute", "Executed"),
]


def run():
	create_workflow_states()
	create_workflow_actions()
	create_workflow()
	frappe.db.commit()
	print("Journey Plan workflow ready.")


def create_workflow_states():
	for state in NEW_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
				ignore_permissions=True
			)


def create_workflow_actions():
	"""Action is also a Link field, not free text — "Review"/"Approve"/
	"Reject" only worked without this because they're standard, pre-
	existing Workflow Action Master records shipped with Frappe.
	"""
	for action in NEW_ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


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
