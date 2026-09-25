# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

"""Create a Hiring Contract from an approved Fleet Hiring Request.

Only available once the request's workflow_state is "Approved" (the final,
submitted state of its approval chain — see
oerp_custom.oerp_custom.doctype.fleet_hiring_request.setup_workflow).

Equipment rows carry over as contract line items: equipment -> equipment,
frequency -> frequency, duration -> qty. Rate and Vehicle Number are left for
the user to fill in on the contract — they aren't known at request time.
"""

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

CONTRACT_NAMING_SERIES = "ALG/T-L/CA/.YY./.#####"


@frappe.whitelist()
def create_hiring_contract(source_name, target_doc=None):
	source = frappe.get_doc("Fleet Hiring Request", source_name)

	if source.workflow_state != "Approved":
		frappe.throw(
			_("A Hiring Contract can only be created from an Approved Fleet Hiring Request.")
		)

	# Only a submitted (Approved) contract blocks a new one — a Rejected or
	# still-in-progress one is docstatus 0 and was never live, so there's
	# nothing to cancel; the user should just be able to try again.
	existing = frappe.db.exists(
		"Hiring Contract",
		{"fleet_hiring_request": source_name, "docstatus": 1},
	)
	if existing:
		frappe.throw(
			_("A Hiring Contract {0} already exists for this request. Cancel it first to create another.").format(
				frappe.bold(existing)
			)
		)

	def set_missing_values(source, target):
		# get_mapped_doc copies over any field the source and target share
		# by name — Fleet Hiring Request and Hiring Contract both have
		# their own separate workflow_state, so without this a new
		# contract would start pre-set to "Approved" (the request's own
		# final state) instead of its own workflow's actual starting state.
		target.workflow_state = None
		target.naming_series = CONTRACT_NAMING_SERIES
		target.fleet_hiring_request = source.name

	doclist = get_mapped_doc(
		"Fleet Hiring Request",
		source_name,
		{
			"Fleet Hiring Request": {
				"doctype": "Hiring Contract",
				"validation": {"docstatus": ["=", 1]},
			},
			"Fleet Hiring Request Equipment": {
				"doctype": "Hiring Contract Item",
				"field_map": {
					"equipment": "equipment",
					"equipment_name": "equipment_name",
					"frequency": "frequency",
					"duration": "qty",
				},
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist
