"""Material Request approval workflow.

Collapses the full Draft -> Pending Review -> Reviewed -> First Approved ->
Second Approved chain into a shorter Draft -> Pending for Approval ->
Approved path when the request's Purpose (material_request_type) is
Material Transfer or Material Issue — those are internal stock movements,
not purchases, so they don't need the multi-stage buying review, just one
submit + one approval. Every other Purpose keeps going through the full
chain exactly as before.

Not fixture-exported (see hooks.py) since this Workflow predates oerp_custom
and already exists on every real site — this script only needs to run once
per site, not on every bench migrate:

    bench --site <site> execute oerp_custom.overrides.material_request_workflow_setup.run

Reusing this exact script both locally (where the Workflow doesn't exist yet,
so BASE_WORKFLOW below recreates the production definition faithfully first)
and on production (where it already exists, so the create step is skipped and
only the shortcut states/transitions below are added/updated) keeps both in
sync with the same source.
"""

import frappe

DOCTYPE = "Material Request"
SHORTCUT_TYPES = ("Material Transfer", "Material Issue")

SHORTCUT_STATES = [
	{"state": "Pending for Approval", "doc_status": "0", "allow_edit": "MR Requester"},
	{"state": "Approved", "doc_status": "1", "allow_edit": "Purchase Manager"},
]

SHORTCUT_TRANSITIONS = [
	{"state": "Draft", "action": "Send for Approval", "next_state": "Pending for Approval", "allowed": "MR Requester", "allow_self_approval": 1},
	{"state": "Pending for Approval", "action": "Approve", "next_state": "Approved", "allowed": "Purchase Manager", "allow_self_approval": 1},
]

# The workflow as it already exists on production — reproduced here only so
# a site that doesn't have it yet (e.g. this dev site) ends up with the same
# baseline before the shortcut states/transitions below are layered on.
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
		_ensure_states_and_actions_exist()
		doc = frappe.get_doc("Workflow", DOCTYPE)

	_restrict_full_chain_to_other_purposes(doc)
	_remove_old_direct_shortcut(doc)
	_add_shortcut_states(doc)
	_add_shortcut_transitions(doc)

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	print("Material Request workflow updated.")


def _ensure_states_and_actions_exist():
	"""State/Action are Link fields, not free text (see the Journey Plan
	workflow setup for the same requirement) — "Pending for Approval" and
	"Approved" are new names, so they need creating as master records
	before any Workflow document can reference them.
	"""
	all_states = [s["state"] for s in BASE_WORKFLOW["states"]] + [s["state"] for s in SHORTCUT_STATES]
	for state in all_states:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
				ignore_permissions=True
			)

	all_actions = {t["action"] for t in BASE_WORKFLOW["transitions"]} | {t["action"] for t in SHORTCUT_TRANSITIONS}
	for action in all_actions:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def _restrict_full_chain_to_other_purposes(doc):
	"""The existing Draft -> Pending Review step is the start of the
	multi-stage (buying) path — it should no longer be offered for the two
	Purposes that now get the shortcut path instead.
	"""
	for t in doc.transitions:
		if t.state == "Draft" and t.action == "Sent for Review":
			t.condition = f"doc.material_request_type not in {SHORTCUT_TYPES!r}"


def _remove_old_direct_shortcut(doc):
	"""An earlier version of this script added a direct Draft -> Second
	Approved transition (single click, no intermediate state) for these two
	Purposes. Superseded by the Pending for Approval step below — remove it
	if present so it doesn't linger as a second, redundant path.
	"""
	doc.transitions = [
		t for t in doc.transitions
		if not (t.state == "Draft" and t.action == "Approve" and t.next_state == "Second Approved"
			and t.condition and "Material Transfer" in t.condition)
	]


def _add_shortcut_states(doc):
	existing_state_names = {s.state for s in doc.states}
	for state in SHORTCUT_STATES:
		if state["state"] not in existing_state_names:
			doc.append("states", state)


def _add_shortcut_transitions(doc):
	condition = f"doc.material_request_type in {SHORTCUT_TYPES!r}"
	for transition in SHORTCUT_TRANSITIONS:
		existing = next(
			(
				t for t in doc.transitions
				if t.state == transition["state"] and t.next_state == transition["next_state"]
			),
			None,
		)
		if existing:
			existing.action = transition["action"]
			existing.allowed = transition["allowed"]
			existing.allow_self_approval = transition["allow_self_approval"]
			existing.condition = condition
		else:
			doc.append("transitions", {**transition, "condition": condition})
