# ALYF Banking Copilot Instructions

Read `CLAUDE.md` in the repository root first. It describes the architecture, the test setup, the code style and the commit message format. For general Frappe development and review rules, use the installed skills `frappe-app-dev`, `frappe-code-review`, `code-style` and `technical-writing`. This file only adds what is specific to Copilot or not covered there.

## Copilot Environment

When you run as GitHub Copilot (coding agent or code review), a ready Frappe bench is available:

- **Bench**: `/home/runner/frappe-bench`. Run all `bench` commands from this directory.
- **Site**: `test_site`, with ERPNext, Payments, HRMS and this app installed. Tests are enabled. Use it as `[sitename]` in the commands from `CLAUDE.md`.
- **App**: `/home/runner/frappe-bench/apps/banking` is a symlink to the repository checkout, so the bench runs the code you see.
- **Pre-commit**: The hooks are installed and run on every commit. Fix what they report.

Use the bench to check your work. Do not rely on reading the code alone:

- **When you change code**: Before you finish, run the tests of each module you changed. If you changed a DocType JSON file or added a patch, run `bench --site test_site migrate` first. Put the commands and their results in the PR description.
- **When you review a pull request**: Before you report a suspected bug, try to confirm it on the bench. Run the related tests, or reproduce the problem with `bench --site test_site execute`. In your comment, say if and how you confirmed the problem.

## Code Rules

Rules that the skills do not cover:

- ❌ `def after_save():` → ✅ Use valid hooks: `after_insert`, `on_update`, `before_save`. Frappe has no `after_save` hook.
- ❌ Change fields in post-save hooks: `self.status = "New"` → ✅ `self.db_set("status", "New")`
- ❌ Change a child table while you iterate over it → ✅ Iterate over a copy of the list
- ❌ `map()`, `filter()` → ✅ List comprehensions
- ❌ DB calls at module level → ✅ Wrap them in functions (multitenancy)
- ❌ `cur_frm` → ✅ `frm` parameter
- ❌ `in_list(list, item)` → ✅ `list.includes(item)`
- ❌ `frappe.utils.debounce(fn, 300)()` → ✅ Create once: `const debounced = frappe.utils.debounce(fn, 300)`

### Translations
- Wrap user-facing strings: `_("Text")` in Python, `__("Text")` in JavaScript
- ❌ `_("Hello {}".format(name))` → ✅ `_("Hello {0}").format(name)`
- ❌ `_("Text") + _("More")` or `_("Long " + "text")` → ✅ `_("Text More")` (one string, no concatenation)
- ❌ `_("")`, `_("{0}")`, `_("  text  ")` → ✅ No empty, placeholder-only or padded strings

### Repository Rules
- HRMS is optional. Custom records for HRMS DocTypes (e.g. **Expense Claim**) are only created when HRMS is installed.
- Never edit DocType JSON files by hand. Change the DocType in the desk or with `bench --site test_site console`, then save it. This runs validations and updates the `modified` timestamp.
- Never log or commit EBICS keys, passphrases, license keys or real bank data (IBANs, transactions).

## Documentation & Communication Style

In PR descriptions, docs and comments:

- **DocTypes** in bold: **Purchase Invoice**, **SEPA Payment Order**
- *Field labels* in italics: *Supplier Bank Account*, *Enable EBICS (New)*
- `field_names` as inline code: `supplier_bank_account`, `enable_ebics`
- Values and report names in quotes: set status to "Completed"
- Prefer labels over field names when you describe functionality to users: ✅ "Set the *Supplier Bank Account* field", ❌ "Set the `supplier_bank_account` field"
