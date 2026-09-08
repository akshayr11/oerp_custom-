import frappe
from frappe.model.naming import make_autoname


def create_tool_registry_records(doc, method):
    """Runs on Stock Entry submit.
    Creates one Tool Registry per unit for items in the 'Tools' item group.
    """
    for row in doc.items:
        item_group = row.get("item_group") or frappe.db.get_value(
            "Item", row.item_code, "item_group"
        )
        if item_group != "Tools":
            continue

        qty = int(row.qty or 0)
        for _ in range(qty):
            tool_no = make_autoname("TL-.MM.-.YY.-.####")

            tool = frappe.new_doc("Tool Registry")
            tool.tool_no = tool_no
            tool.name = tool_no  # force document name = tool_no
            tool.stock_issue_no = doc.name
            tool.item_code = row.item_code
            tool.crew_name = row.get("custom_crew")
            tool.custodian_employee_no = row.get("custom_employee")
            tool.asset_no = row.get("custom_asset_no")
            tool.tool_status = "Active"
            tool.insert(ignore_permissions=True)

    frappe.db.commit()