from datetime import date
from decimal import Decimal
from typing import TypedDict


class BalanceInfo(TypedDict):
	amount: Decimal
	currency: str
	date: date


class SumInfo(TypedDict):
	amount: Decimal
	currency: str
	count: int


class CurrencyAmount(TypedDict):
	amount: Decimal
	currency: str


class MT940SepaInfo(TypedDict):
	EREF: str
	MREF: str
	CRED: str
	SVWZ: str


class MT940Transaction(TypedDict):
	description: str | None
	valuta: date
	date: date | None
	amount: Decimal
	reversal: bool
	booking_key: str
	booking_text: str | None
	reference: str
	bank_reference: str | None
	gvcode: str
	primanota: str | None
	bankcode: str | None
	account: str | None
	iban: str | None
	amount_original: CurrencyAmount | None
	charges: CurrencyAmount | None
	textkey: int | None
	name: list[str]
	purpose: list[str]
	sepa: MT940SepaInfo


class MT940Statement(TypedDict):
	order_reference: str
	reference: str | None
	bankcode: str
	account: str
	number: str
	balance_open: BalanceInfo
	balance_close: BalanceInfo
	balance_booked: BalanceInfo | None
	balance_noted: BalanceInfo | None
	sum_credits: SumInfo | None
	sum_debits: SumInfo | None
	count: int
	transactions: list[MT940Transaction]
