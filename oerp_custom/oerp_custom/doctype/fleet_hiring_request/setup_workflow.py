# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Fleet Hiring Request approval workflow — source of truth for its design.

The Workflow States and Workflow this creates are exported as fixtures
(oerp_custom/fixtures/{workflow_state,workflow}.json), so a plain
`bench migrate` already recreates them on any site — this script does not
need to be run there. It exists so the workflow's shape can be rebuilt or
changed in one place: edit STATES/TRANSITIONS below, rerun this, then
`bench export-fixtures` to refresh the JSON.

    bench --site <site> execute oerp_custom.oerp_custom.doctype.fleet_hiring_request.setup_workflow.run

Creates the three new Workflow States this chain needs (Draft/Approved/
Rejected/Cancelled already exist as shared states), and the Workflow itself:

    Draft -> Site Manager Approval -> Contract Manager Approval
          -> Transport Officer Final Approval -> Approved (submit)

State names describe the approval stages exactly as specified — they are
not roles. Every transition's "allowed" and "allow_edit" is System Manager:
no roles/permissions spec was given for who should actually perform each
step, so nothing is gated by an invented role. Restrict this to real roles
once you have them.

Every state except Approved keeps docstatus 0 — only the final approval
submits the document. Each approval state can also Reject, landing on the
shared "Rejected" state (still docstatus 0). Approved documents can be
Cancelled (docstatus 2).

Rejection Remarks being mandatory on reject is enforced in
oerp_custom.overrides.service_naming / the doctype's own validate() — the
mandatory_depends_on on that field is UI-only in this Frappe version and
does not block anything server-side on its own.
"""

import frappe

DOCTYPE = "Fleet Hiring Request"

# Only the states this workflow introduces. Draft/Approved/Rejected/Cancelled
# already exist as shared Workflow State records on this site.
NEW_STATES = ["Site Manager Approval", "Contract Manager Approval", "Transport Officer Final Approval"]

STATES = [
	# state, doc_status
	("Draft", "0"),
	("Site Manager Approval", "0"),
	("Contract Manager Approval", "0"),
	("Transport Officer Final Approval", "0"),
	("Approved", "1"),
	("Rejected", "0"),
	("Cancelled", "2"),
]

TRANSITIONS = [
	# state, action, next_state
	("Draft", "Review", "Site Manager Approval"),
	("Site Manager Approval", "Approve", "Contract Manager Approval"),
	("Site Manager Approval", "Reject", "Rejected"),
	("Contract Manager Approval", "Approve", "Transport Officer Final Approval"),
	("Contract Manager Approval", "Reject", "Rejected"),
	("Transport Officer Final Approval", "Approve", "Approved"),
	("Transport Officer Final Approval", "Reject", "Rejected"),
	("Approved", "Cancel", "Cancelled"),
]


def run():
	create_workflow_states()
	create_workflow()
	frappe.db.commit()
	print("Fleet Hiring Request workflow ready.")


def create_workflow_states():
	for state in NEW_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
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
