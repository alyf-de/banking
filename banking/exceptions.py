# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from frappe.exceptions import ValidationError


class CurrencyMismatchError(ValidationError):
	"""Raised when two accounts unexpectedly have different currencies."""

	pass
