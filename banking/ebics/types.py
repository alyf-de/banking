from typing import TypedDict, List, Optional
from datetime import date
from decimal import Decimal


class BalanceInfo(TypedDict):
	amount: Decimal
	currency: str
	date: date


class SumInfo(TypedDict):
	amount: Decimal
	currency: str
	count: int

class CurrencyAmount(TypedDict):
	amount:   Decimal
	currency: str


class MT940SepaInfo(TypedDict):
	EREF: str
	MREF: str
	CRED: str
	SVWZ: str


class MT940Transaction(TypedDict):
	description: Optional[str]
	valuta: date
	date: Optional[date]
	amount: Decimal
	reversal: bool
	booking_key: str
	booking_text: Optional[str]
	reference: str
	bank_reference: Optional[str]
	gvcode: str
	primanota: Optional[str]
	bankcode: Optional[str]
	account: Optional[str]
	iban: Optional[str]
	amount_original: Optional[CurrencyAmount]
	charges: Optional[CurrencyAmount]
	textkey: Optional[int]
	name: List[str]
	purpose: List[str]
	sepa: MT940SepaInfo


class MT940Statement(TypedDict):
	order_reference: str
	reference: Optional[str]
	bankcode: str
	account: str
	number: str
	balance_open: BalanceInfo
	balance_close: BalanceInfo
	balance_booked: Optional[BalanceInfo]
	balance_noted: Optional[BalanceInfo]
	sum_credits: Optional[SumInfo]
	sum_debits: Optional[SumInfo]
	count: int
	transactions: List[MT940Transaction]