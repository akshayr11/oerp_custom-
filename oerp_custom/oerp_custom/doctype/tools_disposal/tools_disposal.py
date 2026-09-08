import frappe
from frappe.model.document import Document


class ToolsDisposal(Document):
    def validate(self):
        seen = set()
        for row in self.tools:
            if not row.tool_no:
                frappe.throw(f"Row {row.idx}: Tool No is required")
            if row.tool_no in seen:
                frappe.throw(f"Row {row.idx}: Tool {row.tool_no} is listed more than once")
            seen.add(row.tool_no)

            status = frappe.db.get_value("Tool Registry", row.tool_no, "tool_status")
            if status == "Disposed":
                frappe.throw(f"Row {row.idx}: Tool {row.tool_no} is already Disposed")

    def on_submit(self):
        for row in self.tools:
            frappe.db.set_value("Tool Registry", row.tool_no, "tool_status", "Disposed")

        frappe.db.commit()

    def on_cancel(self):
        for row in self.tools:
            frappe.db.set_value("Tool Registry", row.tool_no, "tool_status", "Active")

        frappe.db.commit()