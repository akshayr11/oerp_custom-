import json

import frappe
from erpnext.stock.get_item_details import get_item_details as _get_item_details


@frappe.whitelist()
def get_item_details(*args, **kwargs):
	"""Workaround for https://github.com/frappe/erpnext/issues/51345.

	Frappe's automatic argument-type coercion (frappe/utils/typing_validations.py)
	tries to validate the incoming ctx/args value against get_item_details'
	`frappe._dict` type hint using pydantic's validate_python -- which only
	accepts an already-constructed dict, not a JSON string. The client sends
	ctx as a JSON string (frappe.call's normal behavior for complex args), so
	validation throws before the real function body ever runs.

	This wrapper intercepts the call first, manually parses any JSON-string
	argument into a frappe._dict, then calls the real implementation
	directly -- bypassing the layer that raises the error.

	frappe.call() also injects a "cmd" key into kwargs (the dotted method
	path being invoked) that the real function doesn't accept -- normally
	frappe filters this out via its own internal argument matching before
	calling the target, but since this wrapper forwards kwargs generically,
	it has to strip that key itself.
	"""
	kwargs.pop("cmd", None)

	for key in ("ctx", "args"):
		if key in kwargs and isinstance(kwargs[key], str):
			kwargs[key] = frappe._dict(json.loads(kwargs[key]))

	return _get_item_details(*args, **kwargs)
