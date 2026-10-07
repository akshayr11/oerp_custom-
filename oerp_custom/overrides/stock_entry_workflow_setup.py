"""Stock Entry approval workflow.

Two Purposes get their own short workflow; every other Purpose (Material
Receipt, Manufacture, Repack, Send to Subcontractor, etc.) is left exactly
as standard Frappe/ERPNext behaves — submit directly, no workflow gate —
via a plain pass-through Draft -> Submitted transition, so this workflow
being active for the whole "Stock Entry" doctype doesn't block every other
Purpose from being submitted at all (a Workflow active for a doctype hides
the native Submit button; without this catch-all, anything other than
Transfer/Issue would be stuck in Draft with no way to submit).

    Material Transfer: Draft -> Pending for Receipt -> Received
                        Submission happens only at Receipt (Pending for
                        Receipt stays docstatus 0 even though the transfer
                        may be physically in progress).

    Material Issue:    Draft -> Pending for Approval -> Approved

No roles were specified, so every transition here is System Manager only —
restrict to real roles once you have them (same convention as every other
workflow built in this app).

Exported as a fixture (oerp_custom/fixtures/workflow.json) via hooks.py, so
a plain `bench migrate` recreates it on any site — this script only needs
running once, to create it the first time (or to pick up a definition
change):

    bench --site <site> execute oerp_custom.overrides.stock_entry_workflow_setup.run
"""

import frappe

DOCTYPE = "Stock Entry"
TRANSFER_PURPOSE = "Material Transfer"
ISSUE_PURPOSE = "Material Issue"

STATES = [
	("Draft", "0"),
	("Pending for Receipt", "0"),
	("Received", "1"),
	("Pending for Approval", "0"),
	("Approved", "1"),
	("Submitted", "1"),
	("Cancelled", "2"),
]

TRANSITIONS = [
	("Draft", "Send for Receipt", "Pending for Receipt", f"doc.purpose == '{TRANSFER_PURPOSE}'"),
	("Pending for Receipt", "Receive", "Received", f"doc.purpose == '{TRANSFER_PURPOSE}'"),
	("Draft", "Send for Approval", "Pending for Approval", f"doc.purpose == '{ISSUE_PURPOSE}'"),
	("Pending for Approval", "Approve", "Approved", f"doc.purpose == '{ISSUE_PURPOSE}'"),
	("Draft", "Submit", "Submitted", f"doc.purpose not in ('{TRANSFER_PURPOSE}', '{ISSUE_PURPOSE}')"),
]


def run():
	create_workflow_states()
	create_workflow_actions()
	create_workflow()
	frappe.db.commit()
	print("Stock Entry workflow ready.")


def create_workflow_states():
	for state, _ in STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
				ignore_permissions=True
			)


def create_workflow_actions():
	for _, action, _, _ in TRANSITIONS:
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
	for state, action, next_state, condition in TRANSITIONS:
		doc.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": "System Manager",
				"allow_self_approval": 1,
				"condition": condition,
			},
		)
	doc.insert(ignore_permissions=True)
