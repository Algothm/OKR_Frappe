from __future__ import annotations

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount


def _sendmail(**kwargs) -> None:
	if not EmailAccount.find_outgoing():
		frappe.logger("okr_management").warning(
			"Skipped OKR email notification because no outgoing Email Account is configured"
		)
		return

	try:
		frappe.sendmail(**kwargs)
	except frappe.OutgoingEmailError:
		frappe.logger("okr_management").warning(
			"Skipped OKR email notification because no outgoing Email Account is configured"
		)


def get_notification_config():
	return {
		"for_doctype": {
			"OKR Objective": {"status": ["in", ["Draft", "Active", "At Risk"]]},
			"OKR Key Result": {"status": ["in", ["Draft", "Active", "At Risk"]]},
			"OKR Check In": {"status": ["in", ["Draft", "Submitted"]]},
		}
	}


def notify_assignment(doc, method=None):
	if not getattr(doc, "owner_user", None):
		return
	_sendmail(
		recipients=[doc.owner_user],
		subject=f"New OKR assignment: {doc.doctype} {doc.name}",
		message="You have a new OKR assignment in the OKR Management workspace.",
	)


def notify_progress_review(doc, method=None):
	previous = getattr(doc, "get_doc_before_save", lambda: None)()
	if getattr(doc, "review_status", "Draft") != "Submitted":
		return
	if previous and getattr(previous, "review_status", None) == "Submitted":
		return
	if getattr(doc, "manager_rating", None):
		_sendmail(
			recipients=[doc.reported_by],
			subject=f"OKR review pending for {doc.name}",
			message="Your progress update is pending review.",
		)


def notify_review_status(doc, method=None):
	previous = getattr(doc, "get_doc_before_save", lambda: None)()
	if getattr(doc, "review_status", "Draft") not in {"Approved", "Modified"}:
		return
	if previous and getattr(previous, "review_status", None) in {"Approved", "Modified"}:
		return
	_sendmail(
		recipients=[doc.reviewer],
		subject=f"OKR review completed for {doc.objective}",
		message="A review action has been completed.",
	)


def notify_sprint_completion(doc, method=None):
	previous = getattr(doc, "get_doc_before_save", lambda: None)()
	if getattr(doc, "status", None) != "Closed":
		return
	if previous and getattr(previous, "status", None) == "Closed":
		return
	recipients = [getattr(doc, "owner_user", None)] if getattr(doc, "owner_user", None) else []
	if recipients:
		_sendmail(
			recipients=recipients,
			subject=f"OKR Plan completed: {doc.name}",
			message="The OKR Plan has been completed and closed.",
		)
