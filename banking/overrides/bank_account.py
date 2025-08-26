def before_validate(doc, method):
	"""Remove spaces from IBAN"""
	if doc.iban:
		doc.iban = doc.iban.replace(" ", "")
