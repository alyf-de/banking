Please use the following documentation to create a python class, with "..." as the implementation of each method/property. Please add type hints for each parameter, if available. Please add the docstring for each method/property. Use the original wording and do not omit any details. Please use modern python types, in the style of `list[str]`, or `str | dict`, etc. Do not use Union, List, Optional, etc.

For example:

```python
class EbicsClient:
    """Main EBICS client class."""
    def __init__(self, bank: 'EbicsBank', user: 'EbicsUser' | list['EbicsUser']):
        """Initializes the EBICS client instance.

        Parameters:
        * bank - An instance of EbicsBank.
        * user – An instance of EbicsUser.
        """
            ...

    def BTD(self, btf: 'BusinessTransactionFormat', start: str | date | None = None, end: str | date | None = None, **params):
        """Downloads data with EBICS protocol version 3.0 (H005).

        Parameters:
        * btf - Instance of BusinessTransactionFormat.
        * start - Start date of requested transactions, either as a date object or ISO8601 string.
        * end - End date of requested transactions, either as a date object or ISO8601 string.
        * params: Additional custom order parameters for the request.
        
        Returns: The requested file data."""
        ...

    @property
    def last_trans_id(self) -> str:
        """This attribute stores the transaction id of the last download process (read-only)."""
        ...
```

---

[PASTE DOCUMENTATION HERE]
