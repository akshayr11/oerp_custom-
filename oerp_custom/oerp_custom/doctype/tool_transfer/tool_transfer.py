import frappe
from frappe.model.document import Document


class ToolTransfer(Document):
    def validate(self):
        for row in self.tools:
            if not row.target_location:
                frappe.throw(f"Row {row.idx}: Target Location is required")

    def on_submit(self):
        for row in self.tools:
            if not row.tool_no:
                continue

            tool = frappe.get_doc("Tool Registry", row.tool_no)
            tool.location = row.target_location
            tool.crew_name = row.target_crew
            tool.custodian_employee_no = row.to_employee

            if row.to_asset:
                tool.asset_no = row.to_asset

            tool.save(ignore_permissions=True)

        frappe.db.commit()

    def on_cancel(self):
        for row in self.tools:
            if not row.tool_no:
                continue

            tool = frappe.get_doc("Tool Registry", row.tool_no)
            tool.location = row.source_location
            tool.crew_name = row.from_crew
            tool.custodian_employee_no = row.from_employee

            if row.from_asset:
                tool.asset_no = row.from_asset

            tool.save(ignore_permissions=True)

        frappe.db.commit()