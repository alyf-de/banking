import frappe

session_response = frappe._dict(
	{
		"consent": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/consent/get",
		"flows":
			{
				"account_details": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/flows/account-details",
				"accounts": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/flows/accounts",
				"balances": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/flows/balances",
				"transactions": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/flows/transactions",
				"transfer": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/flows/transfer"
			},
		"self": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123",
		"session_id": "xyz123",
		"session_id_short": "HB7LM8GT",
        "consent_scope": {
            "lifetime": 90,
            "accounts": {},
            "transactions": {
                "from_date": "2023-01-01",
                "to_date": "2023-03-23"
            }
        }
	}
)

flow_response  = frappe._dict(
	{
		"client_token": "xaBStTc1963.sa3fica234.qSHfI1M0LFYUy-csbwj589598_QW-67",
		"flow_id": "e9fon1j1f03pq329svvrjqid1h2ikutf",
		"self": "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/xyz123/flows/e9fon1j1f03pq329svvrjqid1h2ikutf",
		"state": "CONSUMER_INPUT_NEEDED"
	}
)

bank_data_response = frappe._dict(
    {
        "bank_name": "Testbank",
        "bank_code": "88888888",
        "country_code": "DE",
        "connection": "PSD2",
        "bank_krn": "krn:openbanking:global:bank:269ca6ce-7d5f-4eb0-917a-0fdf8d1cbba9",
        "integration_krn": "krn:openbanking:global:integration:ed45cfda-6774-47ba-a4fc-4b4720865628",
        "sub_integration_krn": "krn:openbanking:global:sub-integration:dd59babd-ba6f-4feb-a26e-ca439ca62f88"
    }
)

consent_response = frappe._dict(
    {
        "consent_id": "4bn7guh6shbl2e",
        "consent_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjNlYWRhNTA4LThlOTAtNDNhNS05NDE0LTk5ZWEwZDQxMTNmZSJ9.eyJ2ZXJzaW9",
        "consents": {
            "accounts": "https://api.openbanking.playground.klarna.com/xs2a/v1/consents/4bn7guh6shbl2e/accounts/get",
            "transactions": "https://api.openbanking.playground.klarna.com/xs2a/v1/consents/4bn7guh6shbl2e/transactions/get"
        }
    }
)

accounts_response_1 = frappe._dict(
	{
		"result": {
			"accounts": [
				{
					"id":"NzRiOWMzOWItNDQxYi00ZGYzLWIyZjItODA5Y2Y1MWFjNzQ0",
					"alias": "My checking account",
					"account_number": "000000005686751168",
					"iban": "DE43000000005686751168",
					"holder_name": "Max Mustermann",
					"bic": "TESTDE10XXX",
					"bank_address": {
						"country": "DE"
					},
					"transfer_type": "FULL",
					"account_type": "DEFAULT",
					"capabilities": {
						"account_details": {
							"available": True
						},
						"transactions": {
							"available": True
						},
						"balances": {
							"available": True
						},
						"transfer": {
							"available": True
						}
					}
				},
				{
					"id": "YmI5NDAzZDctMGNmNi00ZjNiLTkyZGItM2JiNGVkZDM3ZDkw",
					"alias": "My salary account",
					"account_number": "000000006636981175",
					"iban": "DE18000000006636981175",
					"holder_name": "Hans Mustermann",
					"holder_address": {
						"street_address": "Hügelstr. 5",
						"postalcode": "01234",
						"city": "Musterstadt",
						"region": "Hessen",
						"country": "DE"
					},
					"bank_address": {
						"country": "DE"
					},
					"transfer_type": "FULL",
					"account_type": "DEFAULT",
					"capabilities": {
						"account_details": {
							"available": True
						},
						"transactions": {
							"available": True
						},
						"balances": {
							"available": True
						},
						"transfer": {
							"available": True
						}
					}
				},
				{
					"id": "YzQ1MzZlMDQtOGZjNy00YWFlLWEyOTEtNjcyZjYzMTJhM2Q3",
					"alias": "My overdraft account",
					"account_number": "000000004896641138",
					"iban": "DE55000000004896641138",
					"holder_name": "Max Mustermann",
					"bic": "TESTDE10XXX",
					"bank_address": {
						"country": "DE"
					},
					"transfer_type": "FULL",
					"account_type": "DEFAULT",
					"capabilities": {
						"account_details": {
							"available": True
						},
						"transactions": {
							"available": True
						},
						"balances": {
							"available": True
						},
						"transfer": {
							"available": True
						}
					}
				},
				{
					"id": "YTM5ODI4ZWItNjk5NC00NTdhLTkxZjItYzI5ZmExMzU5Y2Nm",
					"alias": "My saving account",
					"account_number": "000000008746441159",
					"iban": "DE28000000008746441159",
					"holder_name": "Max Mustermann",
					"bic": "TESTDE10XXX",
					"bank_address": {
						"country": "DE"
					},
					"transfer_type": "REFERENCE",
					"account_type": "SAVING",
					"capabilities": {
						"account_details": {
							"available": True
						},
						"transactions": {
							"available": True
						},
						"balances": {
							"available": True
						},
						"transfer": {
							"available": False
						}
					}
				},
				{
					"id": "OGFjYWRhNDAtYzJhZC0xMWViLTg1MjktMDI0MmFjMTMwMDAz",
					"alias": "My Restricted account",
					"account_number": "000000008116641159",
					"iban": "DE90000000008116641159",
					"holder_name": "Max Mustermann",
					"bic": "TESTDE10XXX",
					"bank_address": {
						"country": "DE"
					},
					"transfer_type": "RESTRICTED",
					"account_type": "DEFAULT",
					"capabilities": {
						"account_details": {
							"available": True
						},
						"transactions": {
							"available": False
						},
						"balances": {
							"available": False
						},
						"transfer": {
							"available": False
						}
					}
				}
			],
			"type": "accounts",
            "bank_name": "Testbank"
		},
		"client_token": "xaBStTc1963.sa3fica234.qSHfI1M0LFYUy-csbwj589598_QW-67",
		"state": "FINISHED"
	}
)

accounts_response_2 = frappe._dict(
	{
        "result": {
            "accounts": [
                {
                    "id": "0",
                    "alias": "Girokonto (Max Mustermann)",
                    "account_number": "23456789",
                    "iban": "DE06000000000023456789",
                    "holder_name": "Max Mustermann",
                    "bic": "TESTDE20XXX",
                    "transfer_type": "FULL",
                    "account_type": "DEFAULT",
                    "capabilities": {
                        "account_details": {
                            "available": True
                        },
                        "transactions": {
                            "available": True
                        },
                        "balances": {
                            "available": True
                        },
                        "transfer": {
                            "available": True
                        }
                    }
                },
                {
                    "id": "1",
                    "alias": "Girokonto (Musterman, Petra)",
                    "account_number": "2345678902",
                    "iban": "DE86000000002345678902",
                    "holder_name": "Musterman, Petra",
                    "bic": "TESTDE20XXX",
                    "transfer_type": "FULL",
                    "account_type": "DEFAULT",
                    "capabilities": {
                        "account_details": {
                            "available": True
                        },
                        "transactions": {
                            "available": True
                        },
                        "balances": {
                            "available": True
                        },
                        "transfer": {
                            "available": True
                        }
                    }
                },
                {
                    "id": "2",
                    "alias": "Girokonto (Warnecke Hans-Gerd)",
                    "account_number": "12345678",
                    "iban": "DE52000000000012345678",
                    "holder_name": "Warnecke Hans-Gerd",
                    "bic": "TESTDE20XXX",
                    "transfer_type": "FULL",
                    "account_type": "DEFAULT",
                    "capabilities": {
                        "account_details": {
                            "available": True
                        },
                        "transactions": {
                            "available": True
                        },
                        "balances": {
                            "available": True
                        },
                        "transfer": {
                            "available": True
                        }
                    }
                },
                {
                    "id": "3",
                    "alias": "Girokonto (Maria & Josef Warnecke)",
                    "account_number": "1234567899",
                    "iban": "DE30000000001234567899",
                    "holder_name": "Maria & Josef Warnecke",
                    "bic": "TESTDE20XXX",
                    "transfer_type": "FULL",
                    "account_type": "DEFAULT",
                    "capabilities": {
                        "account_details": {
                            "available": True
                        },
                        "transactions": {
                            "available": True
                        },
                        "balances": {
                            "available": True
                        },
                        "transfer": {
                            "available": True
                        }
                    }
                },
                {
                    "id": "4",
                    "alias": "Girokonto (Jürgen Mustermann)",
                    "account_number": "112233",
                    "iban": "DE25000000000000112233",
                    "holder_name": "Jürgen Mustermann",
                    "bic": "TESTDE20XXX",
                    "transfer_type": "FULL",
                    "account_type": "DEFAULT",
                    "capabilities": {
                        "account_details": {
                            "available": True
                        },
                        "transactions": {
                            "available": True
                        },
                        "balances": {
                            "available": True
                        },
                        "transfer": {
                            "available": True
                        }
                    }
                },
                {
                    "id": "5",
                    "alias": "Tagesgeldkonto (Hansi Mustermann)",
                    "account_number": "98765432",
                    "iban": "DE45000000000098765432",
                    "holder_name": "Hansi Mustermann",
                    "bank_code": "00000",
                    "bic": "TESTDE20XXX",
                    "transfer_type": "NONE",
                    "account_type": "SAVING",
                    "capabilities": {
                        "account_details": {
                            "available": False
                        },
                        "transactions": {
                            "available": False
                        },
                        "balances": {
                            "available": False
                        },
                        "transfer": {
                            "available": False
                        }
                    }
                }
            ],
            "type": "accounts",
            "bank_name": "Testbank"
        },
        "client_token": "xaBStTc1963.sa3fica234.qSHfI1M0LFYUy-csbwj589598_QW-67",
        "state": "FINISHED"
    }
)

transactions_consent_response = frappe._dict(
	{
        "result": {
            "transactions": [
                {
                    "transaction_id": "50d18876ee83099984eb0e1ef1c93e3f",
                    "reference": "eBay, Additional information about Ebay",
                    "bank_references": {
                        "unstructured": "eBay",
                        "additional_information": "Additional information about Ebay"
                    },
                    "counter_party": {
                        "id": "YmI5NDAzZDctMGNmNi00ZjNiLTkyZGItM2JiNGVkZDM3ZDkw",
                        "alias": "My salary account",
                        "account_number": "000000006636981175",
                        "iban": "DE18000000006636981175",
                        "holder_name": "Hans Mustermann",
                        "holder_address": {
                            "street_address": "Hügelstr. 5",
                            "postalcode": "01234",
                            "city": "Musterstadt",
                            "region": "Hessen",
                            "country": "DE"
                        },
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-12-02",
                    "value_date": "2022-12-03",
                    "booking_date": "2022-12-02",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 324229,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "a7fdab5b3937e193bcc1ff79934d3e79",
                    "reference": "zalando plus fashion-service 5812871289, Additional information about Zalando",
                    "bank_references": {
                        "unstructured": "zalando plus fashion-service 5812871289",
                        "additional_information": "Additional information about Zalando"
                    },
                    "counter_party": {
                        "id": "ODE5NGNlMzAtZGY2OS00N2JiLTgzNjQtYmI5ZTc4NDljM2Ux",
                        "account_number": "000000008116641159",
                        "iban": "DE90000000008116641159",
                        "holder_name": "Zalando",
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-12-01",
                    "value_date": "2022-12-02",
                    "booking_date": "2022-12-01",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 13990,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "9c59156d4bea01cbc61b73e34bf10588",
                    "reference": "LASTSCHRIFT / BELASTUNG AMAZON PRIME VIDEO END-TO-END-REF.: / MANDATSREF.: GLÄUBIGER-ID: Ref. AMAZON MEDIA EU S.A R.L., Additional information about Amazon",
                    "bank_references": {
                        "unstructured": "LASTSCHRIFT / BELASTUNG AMAZON PRIME VIDEO END-TO-END-REF.: / MANDATSREF.: GLÄUBIGER-ID: Ref. AMAZON MEDIA EU S.A R.L.",
                        "additional_information": "Additional information about Amazon"
                    },
                    "counter_party": {
                        "id": "OWFjYmRmOWItZDY3Ny00MGU2LTg2MjktZWZlYzU5NGI0ZDgw",
                        "account_number": "000000001716448159",
                        "iban": "DE53000000001716448159",
                        "holder_name": "AMAZON MEDIA EU S.A R.L.",
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-12-01",
                    "value_date": "2022-12-02",
                    "booking_date": "2022-12-01",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 6500,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "3cd2c0595fe803ae5bcfb1334568757f",
                    "reference": "transfer, Additional information about the transfer",
                    "bank_references": {
                        "unstructured": "transfer",
                        "additional_information": "Additional information about the transfer"
                    },
                    "counter_party": {
                        "id": "YmI5NDAzZDctMGNmNi00ZjNiLTkyZGItM2JiNGVkZDM3ZDkw",
                        "alias": "My salary account",
                        "account_number": "000000006636981175",
                        "iban": "DE18000000006636981175",
                        "holder_name": "Hans Mustermann",
                        "holder_address": {
                            "street_address": "Hügelstr. 5",
                            "postalcode": "01234",
                            "city": "Musterstadt",
                            "region": "Hessen",
                            "country": "DE"
                        },
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-29",
                    "value_date": "2022-11-29",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 50000,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "aa1fa05ae1d76654da7bd271b645c30a",
                    "reference": "Netflix 2388191, Additional information about Netflix",
                    "bank_references": {
                        "unstructured": "Netflix 2388191",
                        "additional_information": "Additional information about Netflix"
                    },
                    "counter_party": {
                        "id": "ODI4ODRjZjAtODU0MS00MjY1LThhN2UtYTk5NjYwMGMxNGZj",
                        "holder_name": "Netflix",
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-28",
                    "value_date": "2022-11-29",
                    "booking_date": "2022-11-28",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 1199,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "2c1de6e0c8798ff6ca511284341d56ab",
                    "reference": "Thanks for the coffee, Additional information about that coffee",
                    "bank_references": {
                        "unstructured": "Thanks for the coffee",
                        "additional_information": "Additional information about that coffee"
                    },
                    "counter_party": {
                        "id": "ZDFiYzc1YzEtNmRiOS00ODY1LTk1NTYtMjg5YjdkMGNkYzQ4",
                        "account_number": "000000002716442159",
                        "iban": "DE18000000002716442159",
                        "holder_name": "Angela Murkel",
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-28",
                    "value_date": "2022-11-29",
                    "booking_date": "2022-11-28",
                    "state": "PROCESSED",
                    "type": "CREDIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 580,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "7719b188bf37724c8102d55a7223a54f",
                    "reference": "523628918, Additional information",
                    "bank_references": {
                        "unstructured": "523628918",
                        "additional_information": "Additional information"
                    },
                    "counter_party": {
                        "id": "YjYyODYzMzgtNTExZi00MDQyLThmY2MtMzkyNjU5NGI1MGI3",
                        "holder_name": "Spotify",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-28",
                    "value_date": "2022-11-29",
                    "booking_date": "2022-11-28",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 7791,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "4b020576191ebc04b9d44921cd34e6ef",
                    "reference": "REWE SAGT DANKE. 1251611//Linden/DE, Additional information about Rewe",
                    "bank_references": {
                        "unstructured": "REWE SAGT DANKE. 1251611//Linden/DE",
                        "additional_information": "Additional information about Rewe"
                    },
                    "counter_party": {
                        "id": "MzUwNWZiZDMtMDBhMy00ODk2LWI1NTMtYTdkOWI5Njc4MzI3",
                        "holder_name": "REWE Alexander Mar",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-27",
                    "value_date": "2022-11-28",
                    "booking_date": "2022-11-27",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 2320,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "463b8c45f4aceb228d4600b6343f3791",
                    "reference": "302-123123-1900368 AMZN Mktp DE HEWEHASQE, Additional information about Amazon",
                    "bank_references": {
                        "unstructured": "302-123123-1900368 AMZN Mktp DE HEWEHASQE",
                        "additional_information": "Additional information about Amazon"
                    },
                    "counter_party": {
                        "id": "NWI4NzVjMDktZDQ0OC00NzY4LWJjM2QtOTc4NTM2YzY3YjIw",
                        "holder_name": "AMAZON PAYMENTS EUROPE S.C.A.",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-24",
                    "value_date": "2022-11-25",
                    "booking_date": "2022-11-24",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 4999,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "b8a1dca24c632eb8ec5e9d825344b534",
                    "reference": "VK 3543774/WETTENBERGRING 1/ ABHOCHS 20,00 ABWA+Mittelhess.Wasserbetriebe, Additional information about ABWA",
                    "bank_references": {
                        "unstructured": "VK 3543774/WETTENBERGRING 1/ ABHOCHS 20,00 ABWA+Mittelhess.Wasserbetriebe",
                        "additional_information": "Additional information about ABWA"
                    },
                    "counter_party": {
                        "id": "ZDUzMTk3YjUtZGFhZS00M2UyLWIzMjAtNTdiZmYwNjRmYjE3",
                        "holder_name": "Stadtwerke Giessen AG",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-23",
                    "booking_date": "2022-11-23",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 15200,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "a7b08375d13ebbee08d3cb7a133d1b5b",
                    "reference": "Miete + Nebenkosten, Additional information about the rent",
                    "bank_references": {
                        "unstructured": "Miete + Nebenkosten",
                        "additional_information": "Additional information about the rent"
                    },
                    "counter_party": {
                        "id": "NDc1MjZiOGYtMjhmZi00OWRjLWI0NDQtZWRkYTFiMTM1Mzcz",
                        "account_number": "000000003716541159",
                        "iban": "DE02000000003716541159",
                        "holder_name": "Franz Maier",
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-21",
                    "value_date": "2022-11-22",
                    "booking_date": "2022-11-21",
                    "state": "PROCESSED",
                    "type": "CREDIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 75000,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "66c1ece556154678377390481f81cf72",
                    "reference": "Cancelled: Kd-Nr..260293061,Rg-Nr..273723473/5,Mehr Infosunter.Ihre Mobilfunkrechnung., Additional information about the cancellation",
                    "bank_references": {
                        "unstructured": "Cancelled: Kd-Nr..260293061,Rg-Nr..273723473/5,Mehr Infosunter.Ihre Mobilfunkrechnung.",
                        "additional_information": "Additional information about the cancellation"
                    },
                    "counter_party": {
                        "id": "Y2U5ZDExOGEtZTUyZC00NDA4LTlhZGItYWU3MTQyNDdiYzY0",
                        "account_number": "000000004716441199",
                        "iban": "DE46000000004716441199",
                        "holder_name": "Telefonica Germany GmbH + Co. OHG",
                        "transfer_type": "FULL"
                    },
                    "date": "2022-11-21",
                    "value_date": "2022-11-22",
                    "booking_date": "2022-11-21",
                    "state": "CANCELED",
                    "type": "DEBIT",
                    "method": "DIRECT_DEBIT",
                    "amount": {
                        "amount": 2500,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "d5098dc4868fc8c8ffa4249f255f4b7c",
                    "reference": "Rundfunk 01.2019 - 03.2019 Beitragsnr. 61261261Aenderungen ganz bequem. www.rundfunkbeitrag.de, Additional information about the contract",
                    "bank_references": {
                        "unstructured": "Rundfunk 01.2019 - 03.2019 Beitragsnr. 61261261Aenderungen ganz bequem. www.rundfunkbeitrag.de",
                        "additional_information": "Additional information about the contract"
                    },
                    "counter_party": {
                        "id": "NGQ5NWMxZTgtNDFjMS00YTQ0LWFjZWItMzhlMzc0Yzc5M2E0",
                        "account_number": "000000005716441119",
                        "iban": "DE27000000005716441119",
                        "holder_name": "Rundfunk ARD, ZDF, DRadio",
                        "transfer_type": "FULL"
                    },
                    "date": "2022-11-18",
                    "value_date": "2022-11-19",
                    "booking_date": "2022-11-18",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 5250,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "0a17cd586421d8d0acf8496b52e2e6d6",
                    "reference": "transfer, Additional information about the transfer",
                    "bank_references": {
                        "unstructured": "transfer",
                        "additional_information": "Additional information about the transfer"
                    },
                    "counter_party": {
                        "id": "YmI5NDAzZDctMGNmNi00ZjNiLTkyZGItM2JiNGVkZDM3ZDkw",
                        "alias": "My salary account",
                        "account_number": "000000006636981175",
                        "iban": "DE18000000006636981175",
                        "holder_name": "Hans Mustermann",
                        "holder_address": {
                            "street_address": "Hügelstr. 5",
                            "postalcode": "01234",
                            "city": "Musterstadt",
                            "region": "Hessen",
                            "country": "DE"
                        },
                        "transfer_type": "FULL",
                        "account_type": "DEFAULT"
                    },
                    "date": "2022-11-17",
                    "value_date": "2022-11-17",
                    "booking_date": "2022-11-17",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 15000,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "4910a6ba29252a018c650151a3cf311c",
                    "reference": "Uber transfer, 4541fce0-fba6-45bf-a0c2-ff176da98476, Additional information about Uber",
                    "bank_references": {
                        "unstructured": "Uber transfer",
                        "end_to_end": "4541fce0-fba6-45bf-a0c2-ff176da98476",
                        "additional_information": "Additional information about Uber"
                    },
                    "counter_party": {
                        "id": "MzNkOGRlNzEtYTVkMy00M2Q2LTgwMzctOGZlZTRiNGUzMmU2",
                        "account_number": "000000005478456489",
                        "iban": "DE69000000005478456489",
                        "holder_name": "Uber",
                        "transfer_type": "FULL"
                    },
                    "date": "2022-11-16",
                    "value_date": "2022-11-17",
                    "booking_date": "2022-11-16",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 571,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "486a861fd6f9b3ec77979c666228bf10",
                    "reference": "b6a6616c-8c39-4576-a560-6db75fe4d41e, Additional information",
                    "bank_references": {
                        "end_to_end": "b6a6616c-8c39-4576-a560-6db75fe4d41e",
                        "additional_information": "Additional information"
                    },
                    "counter_party": {
                        "id": "MzNkOGRlNzEtYTVkMy00M2Q2LTgwMzctOGZlZTRiNGUzMmU2",
                        "account_number": "000000005478456489",
                        "iban": "DE69000000005478456489",
                        "holder_name": "Uber",
                        "transfer_type": "FULL"
                    },
                    "date": "2022-11-16",
                    "value_date": "2022-11-16",
                    "booking_date": "2022-11-16",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 197,
                        "currency": "EUR"
                    }
                },
                {
                    "transaction_id": "9649ebf4bdc358a5e029a15626964e4a",
                    "reference": "Uber Eats meal 278591, RF369912345678901234588, Klarna AB, Additional information about Uber Eats",
                    "bank_references": {
                        "structured": "Uber Eats meal 278591",
                        "message": "Klarna AB",
                        "additional_information": "Additional information about Uber Eats",
                        "national": "RF369912345678901234588"
                    },
                    "counter_party": {
                        "id": "ZDllMjBmMTAtMzFhNi00NzBkLWFiOTQtMDFjNWZiMjBkMzY1",
                        "account_number": "000000007382156416",
                        "iban": "DE72000000007382156416",
                        "holder_name": "Uber Eats",
                        "transfer_type": "FULL"
                    },
                    "date": "2022-11-15",
                    "value_date": "2022-11-16",
                    "booking_date": "2022-11-15",
                    "state": "PROCESSED",
                    "type": "DEBIT",
                    "method": "TRANSFER",
                    "amount": {
                        "amount": 2471,
                        "currency": "EUR"
                    }
                }
            ],
            "from_date": "2022-01-01",
            "to_date": "2022-12-08",
            "pagination": {}
        },
        "consent_token": "bca38b24a804aa37d821d31af00f5598230122c5bbfc4c4ad5ed40e4258f04ca"
    }
)