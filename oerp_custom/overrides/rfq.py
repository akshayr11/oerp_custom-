import frappe


@frappe.whitelist()
def create_sq_comparison_from_rfq(rfq):
    """
    Creates an SQ Comparison document from an approved Request for Quotation.
    Only pulls in items from Supplier Quotations where workflow_state = 'Approved'.

    Called from client script via:
        frappe.call({
            method: 'oerp_custom.oerp_custom.overrides.rfq.create_sq_comparison_from_rfq',
            args: { rfq: frm.doc.name }
        })
    """

    rfq_doc = frappe.get_doc("Request for Quotation", rfq)

    # Get all Supplier Quotation Items linked to this RFQ
    sq_items = frappe.get_all(
        "Supplier Quotation Item",
        filters={"request_for_quotation": rfq},
        fields=[
            "name", "parent", "item_code", "item_name", "brand", "qty", "uom",
            "rate", "material_request", "material_request_item"
        ]
    )

    if not sq_items:
        frappe.throw("No Supplier Quotation Items found for this RFQ.")

    sq_parents = list(set(d.parent for d in sq_items))

    # Only keep Supplier Quotations that are Approved
    approved_sqs = frappe.get_all(
        "Supplier Quotation",
        filters={
            "name": ["in", sq_parents],
            "workflow_state": "Approved",
            "docstatus": 1
        },
        fields=["name", "supplier", "currency"]
    )

    if not approved_sqs:
        frappe.throw("No Approved Supplier Quotations found for this RFQ.")

    approved_map = {d.name: d for d in approved_sqs}

    comparison = frappe.new_doc("SQ Comparison")
    comparison.request_for_quotation = rfq

    for item in sq_items:
        if item.parent not in approved_map:
            continue
        sq = approved_map[item.parent]
        comparison.append("approved_suppliers", {
            "approved_supplier": sq.supplier,
            "item": item.item_code,
            "item_name": item.item_name,
            "brand": item.brand,
            "qty": item.qty,
            "uom": item.uom,
            "rate": item.rate,
            "price": (item.rate or 0) * (item.qty or 0),
            "currency": sq.currency,
            "request_for_quotation": rfq,
            "material_request": item.material_request,
            "material_request_item": item.material_request_item,
            "supplier_quotation": item.parent,
            "supplier_quotation_item": item.name
        })

    comparison.insert()
    return comparison.name


@frappe.whitelist()
def get_approved_supplier_quotations(rfq):
    """
    Returns True if at least one Supplier Quotation linked to this RFQ
    is in workflow_state = 'Approved'. Used to conditionally show the
    SQ Comparison button on the RFQ form.
    """

    sq_names = frappe.get_all(
        "Supplier Quotation Item",
        filters={"request_for_quotation": rfq},
        pluck="parent",
        distinct=True
    )

    if not sq_names:
        return False

    approved_count = frappe.db.count(
        "Supplier Quotation",
        filters={
            "name": ["in", sq_names],
            "workflow_state": "Approved",
            "docstatus": 1
        }
    )

    return approved_count > 0