app_name = "oerp_custom"
app_title = "Oerp Custom"
app_publisher = "akshay"
app_description = "akshay"
app_email = "akshay.r.ravi@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "oerp_custom",
# 		"logo": "/assets/oerp_custom/logo.png",
# 		"title": "Oerp Custom",
# 		"route": "/oerp_custom",
# 		"has_permission": "oerp_custom.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/oerp_custom/css/oerp_custom.css"
# app_include_js = "/assets/oerp_custom/js/oerp_custom.js"

# include js, css files in header of web template
# web_include_css = "/assets/oerp_custom/css/oerp_custom.css"
# web_include_js = "/assets/oerp_custom/js/oerp_custom.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "oerp_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_list_js = {
    "Purchase Order": "public/js/purchase_order_list.js"
}

doctype_js = {
    "Purchase Order": "public/js/purchase_order.js",
    "Material Request": "public/js/material_request.js",
    "Purchase Receipt": "public/js/purchase_receipt.js",
    "Request for Quotation": "public/js/rfq.js",
    "Supplier": "public/js/supplier.js",
    "Supplier Quotation": "public/js/supplier_quotation.js",
    "Payment Entry": "public/js/payment_entry.js",
}

doc_events = {
    "Purchase Order": {
        # frappe names the doc BEFORE validate on insert, so the series is
        # fixed in before_insert and only verified (warned) in validate.
        "before_insert": "oerp_custom.overrides.service_naming.before_insert_purchase_order",
        "validate": [
            "oerp_custom.overrides.purchase_order.validate_contract_scope",
            # Series follows purchase_type: Service -> PUR-SER, Contract -> PUR-CON.
            "oerp_custom.overrides.service_naming.apply_po_naming",
        ],
    },
    "Material Request": {
        "before_insert": "oerp_custom.overrides.service_naming.before_insert_material_request",
        # By Service: SER-MR series, Service Type mandatory, service items only.
        "validate": "oerp_custom.overrides.service_naming.validate_material_request",
    },
    "Stock Entry": {
        "on_submit": "oerp_custom.overrides.stock_entry.create_tool_registry_records"
    },
    "Item": {
        "validate": "oerp_custom.overrides.item.sync_qty_level_to_reorder"
    }
}

# A PO raised from a service Material Request arrives already typed as Service,
# with the Service Type and the PUR-SER series carried across.
override_whitelisted_methods = {
    "erpnext.stock.doctype.material_request.material_request.make_purchase_order":
        "oerp_custom.overrides.service_naming.make_purchase_order",
    "erpnext.stock.get_item_details.get_item_details":
        "oerp_custom.overrides.get_item_details_patch.get_item_details",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "oerp_custom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "oerp_custom.utils.jinja_methods",
# 	"filters": "oerp_custom.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "oerp_custom.install.before_install"
# after_install = "oerp_custom.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "oerp_custom.uninstall.before_uninstall"
# after_uninstall = "oerp_custom.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "oerp_custom.utils.before_app_install"
# after_app_install = "oerp_custom.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "oerp_custom.utils.before_app_uninstall"
# after_app_uninstall = "oerp_custom.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "oerp_custom.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "oerp_custom.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"oerp_custom.tasks.all"
# 	],
# 	"daily": [
# 		"oerp_custom.tasks.daily"
# 	],
# 	"hourly": [
# 		"oerp_custom.tasks.hourly"
# 	],
# 	"weekly": [
# 		"oerp_custom.tasks.weekly"
# 	],
# 	"monthly": [
# 		"oerp_custom.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "oerp_custom.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "oerp_custom.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "oerp_custom.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "oerp_custom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["oerp_custom.utils.before_request"]
# after_request = ["oerp_custom.utils.after_request"]

# Job Events
# ----------
# before_job = ["oerp_custom.utils.before_job"]
# after_job = ["oerp_custom.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"oerp_custom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

