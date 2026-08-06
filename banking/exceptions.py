# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from frappe.exceptions import ValidationError


class CurrencyMismatchError(ValidationError):
	"""Raised when two accounts unexpectedly have different currencies."""

	pass


class FullReconciliationRequiredError(ValidationError):
	"""Raised when an action requires reconciling the whole transaction at once."""

	pass


class PartyMismatchError(ValidationError):
	"""Raised when a party cannot be booked against the given account."""

	pass
