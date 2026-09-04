app_name = "okr_management"
app_title = "OKR Management"
app_publisher = " Ajanta Bottles"
app_description = "OKR Management System for ERPNext"
app_email = "utsav@algothm.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "okr_management",
# 		"logo": "/assets/okr_management/logo.png",
# 		"title": "OKR Management",
# 		"route": "/okr_management",
# 		"has_permission": "okr_management.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/okr_management/css/okr_management.css"
app_include_js = "/assets/okr_management/js/okr_management.js?v=20260904-1"

# include js, css files in header of web template
# web_include_css = "/assets/okr_management/css/okr_management.css"
# web_include_js = "/assets/okr_management/js/okr_management.js?v=20260903-5"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "okr_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "okr_management/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "okr_management.utils.jinja_methods",
# 	"filters": "okr_management.utils.jinja_filters"
# }

# Installation
# ------------

before_install = "okr_management.install.before_install"
after_install = "okr_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "okr_management.uninstall.before_uninstall"
# after_uninstall = "okr_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "okr_management.utils.before_app_install"
# after_app_install = "okr_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "okr_management.utils.before_app_uninstall"
# after_app_uninstall = "okr_management.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

notification_config = "okr_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"OKR Plan": "okr_management.permissions.get_plan_permission_query_conditions",
	"OKR Objective": "okr_management.hierarchy_visibility.objective_query",
	"OKR Key Result": "okr_management.hierarchy_visibility.key_result_query",
	"OKR Check In": "okr_management.hierarchy_visibility.checkin_query",
	"OKR Action Item": "okr_management.hierarchy_visibility.action_item_query",
	"Group": "okr_management.permissions.get_group_permission_query_conditions",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {}


# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": ["okr_management.tasks.daily"],
	"hourly": ["okr_management.tasks.hourly"],
}

# Testing
# -------

# before_tests = "okr_management.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.desk.desktop.get_workspace_sidebar_items": "okr_management.navigation.get_workspace_sidebar_items",
}

# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "okr_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "okr_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["okr_management.utils.before_request"]
# after_request = ["okr_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["okr_management.utils.before_job"]
# after_job = ["okr_management.utils.after_job"]

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
# 	"okr_management.auth.validate"
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


has_permission = {
	"OKR Plan": "okr_management.permissions.has_plan_permission",
	"OKR Objective": "okr_management.hierarchy_visibility.objective_permission",
	"OKR Key Result": "okr_management.hierarchy_visibility.key_result_permission",
	"OKR Action Item": "okr_management.hierarchy_visibility.action_item_permission",
	"OKR Check In": "okr_management.hierarchy_visibility.checkin_permission",
	"Group": "okr_management.permissions.has_group_permission",
}


# Keep OKR Plan/Objectives/KRs/Actions/Check-Ins as direct Desk routes.
boot_session = "okr_management.boot.boot_session"
