import frappe

DEFAULT_REQUEST_TYPE = "Purchase"


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