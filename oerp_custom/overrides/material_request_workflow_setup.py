"""Material Request approval workflow.

Collapses the full Draft -> Pending Review -> Reviewed -> First Approved ->
Second Approved chain into a single Purchase Manager approval when the
request's Purpose (material_request_type) is Material Transfer or Material
Issue — those are internal stock movements, not purchases, so they don't
need the multi-stage buying review. Every other Purpose keeps going through
the full chain exactly as before.

Not fixture-exported (see hooks.py) since this Workflow predates oerp_custom
and already exists on every real site — this script only needs to run once
per site, not on every bench migrate:

    bench --site <site> execute oerp_custom.overrides.material_request_workflow_setup.run

Reusing this exact script both locally (where the Workflow doesn't exist yet,
so BASE_WORKFLOW below recreates the production definition faithfully first)
and on production (where it already exists, so the create step is skipped and
only the two target transitions below are added/updated) keeps both in sync
with the same source.
"""

import frappe

DOCTYPE = "Material Request"
SINGLE_APPROVAL_TYPES = ("Material Transfer", "Material Issue")

# The workflow as it already exists on production — reproduced here only so
# a site that doesn't have it yet (e.g. this dev site) ends up with the same
# baseline before the single-approval transitions below are layered on.
BASE_WORKFLOW = {
	"workflow_name": DOCTYPE,
	"document_type": DOCTYPE,
	"is_active": 1,
	"workflow_state_field": "workflow_state",
	"states": [
		{"state": "Draft", "doc_status": "0", "allow_edit": "MR Requester"},
		{"state": "Pending Review", "doc_status": "0", "allow_edit": "MR Requester"},
		{"state": "Reviewed", "doc_status": "0", "allow_edit": "Purchase User"},
		{"state": "First Approved", "doc_status": "0", "allow_edit": "Purchase Manager"},
		{"state": "Second Approved", "doc_status": "1", "allow_edit": "Purchase Manager"},
		{"state": "Cancelled", "doc_status": "2", "allow_edit": "Purchase Manager"},
	],
	"transitions": [
		{"state": "Draft", "action": "Sent for Review", "next_state": "Pending Review", "allowed": "MR Requester", "allow_self_approval": 1},
		{"state": "Pending Review", "action": "Review", "next_state": "Reviewed", "allowed": "Purchase User", "allow_self_approval": 1},
		{"state": "Reviewed", "action": "Approve", "next_state": "First Approved", "allowed": "Purchase Manager", "allow_self_approval": 1},
		{"state": "First Approved", "action": "Approve", "next_state": "Second Approved", "allowed": "Purchase Manager", "allow_self_approval": 1},
	],
}


def run():
	if not frappe.db.exists("Workflow", DOCTYPE):
		_ensure_states_and_actions_exist()
		doc = frappe.new_doc("Workflow")
		doc.update(BASE_WORKFLOW)
		doc.insert(ignore_permissions=True)
	else:
		doc = frappe.get_doc("Workflow", DOCTYPE)

	_restrict_full_chain_to_other_purposes(doc)
	_add_single_approval_transition(doc)

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	print("Material Request workflow updated.")


def _ensure_states_and_actions_exist():
	"""Only needed the first time this runs on a site that doesn't already
	have this Workflow (e.g. a fresh dev site) — production already has
	these as a side effect of the Workflow having been built there via the
	UI. State/Action are Link fields, not free text (see the Journey Plan
	workflow setup for the same requirement).
	"""
	for state in [s["state"] for s in BASE_WORKFLOW["states"]]:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
				ignore_permissions=True
			)

	actions = {t["action"] for t in BASE_WORKFLOW["transitions"]} | {"Approve"}
	for action in actions:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def _restrict_full_chain_to_other_purposes(doc):
	"""The existing Draft -> Pending Review step is the start of the
	multi-stage (buying) path — it should no longer be offered for the two
	Purposes that now get a single-approval shortcut instead.
	"""
	for t in doc.transitions:
		if t.state == "Draft" and t.action == "Sent for Review":
			t.condition = f"doc.material_request_type not in {SINGLE_APPROVAL_TYPES!r}"


def _add_single_approval_transition(doc):
	condition = f"doc.material_request_type in {SINGLE_APPROVAL_TYPES!r}"
	existing = next(
		(t for t in doc.transitions if t.state == "Draft" and t.next_state == "Second Approved"),
		None,
	)
	if existing:
		existing.condition = condition
		existing.allowed = "Purchase Manager"
		existing.allow_self_approval = 1
	else:
		doc.append(
			"transitions",
			{
				"state": "Draft",
				"action": "Approve",
				"next_state": "Second Approved",
				"allowed": "Purchase Manager",
				"allow_self_approval": 1,
				"condition": condition,
			},
		)
