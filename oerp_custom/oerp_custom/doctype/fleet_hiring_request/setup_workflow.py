# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Fleet Hiring Request approval workflow — source of truth for its design.

The roles, Workflow States and Workflow this creates are exported as
fixtures (oerp_custom/fixtures/{role,workflow_state,workflow}.json), so a
plain `bench migrate` already recreates them on any site — this script does
not need to be run there. It exists so the workflow's shape can be rebuilt or
changed in one place: edit STATES/TRANSITIONS below, rerun this, then
`bench export-fixtures` to refresh the JSON.

    bench --site <site> execute oerp_custom.oerp_custom.doctype.fleet_hiring_request.setup_workflow.run

Creates the three approver roles, the three new Workflow States this chain
needs (Draft/Approved/Rejected/Cancelled already exist as shared states), and
the Workflow itself:

    Draft -> Site Manager Approval -> Contract Manager Approval
          -> Transport Officer Final Approval -> Approved (submit)

Every state except Approved keeps docstatus 0 — only the final approval
submits the document. Each approval state can also Reject, landing on the
shared "Rejected" state (still docstatus 0). Approved documents can be
Cancelled (docstatus 2).

Rejection Remarks being mandatory on reject is enforced by the
mandatory_depends_on on that field in fleet_hiring_request.json, not by
anything here — Frappe's own document validation handles it once
workflow_state is set to "Rejected".
"""

import frappe

DOCTYPE = "Fleet Hiring Request"

NEW_ROLES = ["Site Manager", "Contract Manager", "Transport Officer"]

# Only the states this workflow introduces. Draft/Approved/Rejected/Cancelled
# already exist as shared Workflow State records on this site.
NEW_STATES = ["Site Manager Approval", "Contract Manager Approval", "Transport Officer Final Approval"]

STATES = [
	# state, doc_status, allow_edit role
	("Draft", "0", "Employee"),
	("Site Manager Approval", "0", "Site Manager"),
	("Contract Manager Approval", "0", "Contract Manager"),
	("Transport Officer Final Approval", "0", "Transport Officer"),
	("Approved", "1", ""),
	("Rejected", "0", ""),
	("Cancelled", "2", ""),
]

TRANSITIONS = [
	# state, action, next_state, allowed role
	("Draft", "Review", "Site Manager Approval", "Employee"),
	("Site Manager Approval", "Approve", "Contract Manager Approval", "Site Manager"),
	("Site Manager Approval", "Reject", "Rejected", "Site Manager"),
	("Contract Manager Approval", "Approve", "Transport Officer Final Approval", "Contract Manager"),
	("Contract Manager Approval", "Reject", "Rejected", "Contract Manager"),
	("Transport Officer Final Approval", "Approve", "Approved", "Transport Officer"),
	("Transport Officer Final Approval", "Reject", "Rejected", "Transport Officer"),
	("Approved", "Cancel", "Cancelled", "System Manager"),
]


def run():
	create_roles()
	create_workflow_states()
	create_workflow()
	frappe.db.commit()
	print(f"Fleet Hiring Request workflow ready.")


def create_roles():
	for role in NEW_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


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
