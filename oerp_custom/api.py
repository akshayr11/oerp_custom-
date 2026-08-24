import json

import frappe


@frappe.whitelist()
def get_po_attachments(po_names):
	"""Attachments for a set of Purchase Orders, including files attached on the
	item rows (Attach fields on Purchase Order Item store their File against the
	CHILD doctype, not the parent — which is why a plain File query on
	"Purchase Order" never finds them).

	Returns: { po_name: {"total": int, "files": [ {file_name, file_url,
	          item_code, item_row} ] } }  — item_code is None for files attached
	          on the order itself.
	"""
	if isinstance(po_names, str):
		po_names = json.loads(po_names)
	if not po_names:
		return {}

	# Permission gate: only orders the user can actually read.
	allowed = frappe.get_list(
		"Purchase Order", filters={"name": ("in", po_names)}, pluck="name"
	)
	if not allowed:
		return {}

	out = {name: {"total": 0, "files": []} for name in allowed}

	# 1) Files attached directly on the Purchase Order
	for f in frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Purchase Order", "attached_to_name": ("in", allowed)},
		fields=["file_name", "file_url", "attached_to_name", "is_private"],
		order_by="creation",
	):
		out[f.attached_to_name]["files"].append(
			{
				"file_name": f.file_name or f.file_url,
				"file_url": f.file_url,
				"is_private": f.is_private,
				"item_code": None,
				"item_row": None,
			}
		)

	# 2) Files attached on the item rows (Attach fields in the items table)
	item_rows = frappe.get_all(
		"Purchase Order Item",
		filters={"parent": ("in", allowed), "parenttype": "Purchase Order"},
		fields=["name", "parent", "item_code", "idx"],
	)
	row_map = {row.name: row for row in item_rows}

	if row_map:
		for f in frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Purchase Order Item",
				"attached_to_name": ("in", list(row_map)),
			},
			fields=["file_name", "file_url", "attached_to_name", "is_private"],
			order_by="creation",
		):
			row = row_map[f.attached_to_name]
			out[row.parent]["files"].append(
				{
					"file_name": f.file_name or f.file_url,
					"file_url": f.file_url,
					"is_private": f.is_private,
					"item_code": row.item_code,
					"item_row": row.idx,
				}
			)

	for name in out:
		out[name]["total"] = len(out[name]["files"])

	return out
