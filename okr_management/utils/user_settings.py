import json

import frappe


def clear_user_settings_cache(doctype: str) -> None:
	prefix = f"{doctype}::"
	keys = []
	for key in frappe.cache.hkeys("_user_settings"):
		decoded = key.decode() if isinstance(key, bytes) else key
		if decoded.startswith(prefix):
			keys.append(decoded)
	if keys:
		frappe.cache.hdel("_user_settings", *keys)


def reset_list_group_by_fields(doctype: str) -> int:
	rows = frappe.db.sql(
		"select user, data from `__UserSettings` where doctype = %s",
		doctype,
		as_dict=True,
	)
	updated = 0

	for row in rows:
		data = frappe.parse_json(row.data) or {}
		if not isinstance(data, dict):
			continue

		if "group_by_fields" not in data:
			continue

		data.pop("group_by_fields", None)
		frappe.db.sql(
			"update `__UserSettings` set data = %s where doctype = %s and user = %s",
			(json.dumps(data), doctype, row.user),
		)
		updated += 1

	clear_user_settings_cache(doctype)
	frappe.db.commit()
	return updated


def reset_okr_key_result_list_filters() -> int:
	return reset_list_group_by_fields("OKR Key Result")