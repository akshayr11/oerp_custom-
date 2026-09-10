# Copyright (c) 2026, akshay and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServiceType(Document):

    def on_update(self):
        self.create_item_group()

    def create_item_group(self):

        # Validate required fields
        if not self.service_type_name:
            frappe.throw("Service Type Name is required")

        if not self.service_category:
            frappe.throw("Service Category is required")

        # Check if Item Group already exists
        item_group_name = frappe.db.exists(
            "Item Group",
            self.service_type_name
        )

        if item_group_name:
            item_group = frappe.get_doc(
                "Item Group",
                item_group_name
            )

            # Update parent Item Group if changed
            if item_group.parent_item_group != self.service_category:
                item_group.parent_item_group = self.service_category

        else:
            # Create new Item Group
            item_group = frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": self.service_type_name,
                "parent_item_group": self.service_category,
                "is_group": 0
            })

        # Remove old company/account mappings
        item_group.set("item_group_defaults", [])

        # Add company + expense account mappings
        for row in self.company_accounts:

            if not row.company:
                continue

            if not row.expense_account:
                continue

            item_group.append("item_group_defaults", {
                "company": row.company,
                "expense_account": row.expense_account
            })

        # Save / Insert Item Group
        if item_group.is_new():
            item_group.insert(ignore_permissions=True)
        else:
            item_group.save(ignore_permissions=True)
