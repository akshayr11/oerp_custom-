# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""MRF Status by Cost Center.

"MRF" = Material Request (Purpose/material_request_type = Purchase) — the
purchase-workflow request, as distinct from Material Transfer/Issue.

One row per Cost Center, one column per distinct workflow_state value
currently in use on Material Request, cell = count of Material Requests
with that Cost Center that are currently sitting in that state.

Columns are NOT a fixed hardcoded list — they're read live from whatever
workflow_state values actually exist on the site, so this keeps working as
the underlying workflow's states change (new states added, states
renamed), without needing a code change to match.

Cost Center lives on Material Request Item, not the header — a request
whose rows span more than one Cost Center is counted once under each Cost
Center its rows touch.
"""

import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	state_order = get_state_order()
	columns = get_columns(state_order)
	data = get_data(filters, state_order)
	return columns, data


def get_state_order():
	"""Distinct workflow_state values in use, ordered to match the Material
	Request workflow's own state sequence (idx) where that state is known
	to the Workflow doctype, with anything else (e.g. a blank/None state on
	very old records) tacked on at the end.
	"""
	ordered = frappe.db.sql(
		"""
		SELECT DISTINCT ws.state
		FROM `tabWorkflow Transition` ws
		INNER JOIN `tabWorkflow` w ON w.name = ws.parent
		WHERE w.document_type = 'Material Request' AND w.is_active = 1
		ORDER BY ws.idx
		""",
		as_dict=True,
	)
	known = [r.state for r in ordered]

	in_use = frappe.db.sql(
		"""
		SELECT DISTINCT workflow_state
		FROM `tabMaterial Request`
		WHERE material_request_type = 'Purchase' AND workflow_state IS NOT NULL AND workflow_state != ''
		""",
		as_dict=True,
	)
	in_use_states = {r.workflow_state for r in in_use}

	ordered_states = [s for s in known if s in in_use_states]
	extra_states = sorted(in_use_states - set(ordered_states))
	return ordered_states + extra_states


def get_columns(state_order):
	columns = [
		{"label": "Cost Center", "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 220},
	]
	for state in state_order:
		columns.append(
			{
				"label": state,
				"fieldname": frappe.scrub(state),
				"fieldtype": "Int",
				"width": 110,
			}
		)
	return columns


def get_data(filters, state_order):
	conditions = ["mr.material_request_type = 'Purchase'"]
	values = {}

	if filters.get("cost_center"):
		conditions.append("mri.cost_center = %(cost_center)s")
		values["cost_center"] = filters.cost_center

	condition_str = " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		SELECT mri.cost_center AS cost_center, mr.workflow_state AS workflow_state, COUNT(DISTINCT mr.name) AS cnt
		FROM `tabMaterial Request` mr
		INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE {condition_str}
		GROUP BY mri.cost_center, mr.workflow_state
		""",
		values,
		as_dict=True,
	)

	by_cost_center = {}
	for row in rows:
		cc = row.cost_center or "(No Cost Center)"
		by_cost_center.setdefault(cc, {})[row.workflow_state] = row.cnt

	data = []
	for cost_center in sorted(by_cost_center):
		state_counts = by_cost_center[cost_center]
		out_row = {"cost_center": cost_center}
		for state in state_order:
			out_row[frappe.scrub(state)] = state_counts.get(state, 0)
		data.append(out_row)

	return data
