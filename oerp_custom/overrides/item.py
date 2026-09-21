import frappe

DEFAULT_REQUEST_TYPE = "Purchase"


def sync_item_group_from_service_type(doc, method=None):
	"""Item Group (labelled "Item Sub Category" on the form) mirrors the
	selected Service Type value directly, and Item Main Category
	(fieldname item_sub_category — named the opposite of its own label)
	is set to that Item Group's own parent in the Item Group tree.

	Note: item_group is a Link to Item Group, so the first part only
	succeeds if an Item Group named exactly the same as the Service Type
	already exists — otherwise the save fails with an invalid-link error.
	"""
	if not doc.custom_service_type:
		return

	doc.item_group = doc.custom_service_type
	doc.item_sub_category = frappe.db.get_value("Item Group", doc.item_group, "parent_item_group")


def sync_qty_level_to_reorder(doc, method=None):
    for row in doc.get("custom_item_qty_level") or []:
        if not row.store:
            continue

        existing = next(
            (r for r in (doc.get("reorder_levels") or []) if r.warehouse == row.store),
            None,
        )

        values = {
            "warehouse": row.store,
            "warehouse_group": row.store,
            "warehouse_reorder_level": row.minimum or 0,
            "warehouse_reorder_qty": row.maximum or 0,
            "material_request_type": DEFAULT_REQUEST_TYPE,
        }

        if existing:
            existing.update(values)
        else:
            doc.append("reorder_levels", values)