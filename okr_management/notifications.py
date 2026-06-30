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
			"OKR Objective": {
				"notify_on": ["Submitted", "Approved", "Rejected", "At Risk", "Completed"],
				"messages": [
					{"subject": "OKR objective requires review", "message": "An OKR objective needs your attention."},
					{"subject": "New OKR assignment", "message": "You have been assigned a new objective."},
				],
			},
			"OKR Key Result": {
				"notify_on": ["Submitted", "Approved", "At Risk", "Achieved", "Missed", "Closed"],
				"messages": [
					{"subject": "Key result status changed", "message": "A key result status changed and may require follow-up."},
				],
			},
			"OKR Check In": {
				"notify_on": ["Submitted", "Reviewed", "Final"],
				"messages": [
					{"subject": "New OKR check-in submitted", "message": "A check-in was submitted for review."},
				],
			},
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


def notify_cycle_completion(doc, method=None):
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
