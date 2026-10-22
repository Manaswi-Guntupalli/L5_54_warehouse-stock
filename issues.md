# Issues Found and Fixed

## Stock validation and reorder fixes

After the earlier cleanup, I checked two more problems in the stock logic.

| Issue | Type | Location | Description | Fix Approach |
|-------|------|----------|-------------|--------------|
| Negative stock receipts | Input validation | `add_stock()` | A negative quantity reduced inventory even though this function is meant to receive stock. | Reject negative quantities, fractions, Boolean values and other non-integer inputs before changing inventory or history. Also require a nonempty string SKU. |
| Empty products missing from reorder checks | Logic | `remove_stock()` | Removing the last units deleted the SKU, so it no longer appeared in the reorder list. | Keep the SKU with quantity zero so it can still be reported, saved and flagged for replenishment. |

I allowed zero in `add_stock()` so a new product can be registered before any units arrive. Removing stock still requires a positive quantity. I also updated the demo to show invalid receipts being rejected without stopping the program.

I checked that rejected receipts leave both stock and history unchanged. Removing all ten units from a product now leaves it at zero and includes it in `check_reorder()`. The zero quantity survives saving and loading, and receiving enough stock removes the product from the reorder list again. Pylint still scores **10.00/10**, and Flake8 and Bandit both pass. The three reports have been refreshed.

I used the Pylint, Flake8 and Bandit reports to check the warehouse stock manager. I started with the five security issues listed by Bandit and fixed them in priority order: the high-severity issue first, followed by the medium- and low-severity issues.

The line numbers in the table refer to the original code. They have changed because the fixes added more code.

| Issue | Type | Line(s) | Description | Fix Approach |
|-------|------|---------|-------------|--------------|
| Weak MD5 hashing (B324), priority 1 | Security - High | 31 | The SKU checksum used MD5, which Bandit flagged as a weak hash algorithm. In this program, the checksum was used as a short label on warehouse bins. | Replaced MD5 with SHA-256 and kept the first six characters so the printed label format stayed the same. |
| Unsafe `eval()` for stock adjustment (B307), priority 2 | Security - Medium | 62 | The adjustment formula was passed directly to `eval()`. This could execute Python code instead of just calculating a stock quantity. | Added `evaluate_adjustment()` to parse the formula with `ast` and allow only specific arithmetic operations and the name `current`. |
| Unnecessary `eval()` (B307), priority 3 | Security - Medium | 80 | The program used `eval()` just to print the message `stock audit complete`. There was no need to evaluate Python code for this. | Replaced it with a normal `print()` call. |
| Hardcoded password (B105), priority 4 | Security - Low | 10 | The supervisor password was written directly in the source code and repeated in the demo. Anyone reading the file could see it. | Removed both occurrences and used the `WAREHOUSE_SUPERVISOR_PASSWORD` environment variable. Added checks for missing configuration and incorrect passwords. |
| Silent exception handling (B110), priority 5 | Error handling - Low | 23-24 | `remove_stock()` used a bare `except` followed by `pass`. This hid errors, so a failed removal could look like it had worked. | Added input and stock checks that raise specific errors. Updated the demo to catch expected errors and display the reason for rejection. |

## Step 1: Replace MD5

I changed `sku_checksum()` to use `hashlib.sha256()` with UTF-8 encoding. I kept the six-character output because it is used as a short bin label. I also checked that the function returns the expected SHA-256 prefix for a sample SKU.

The short label can still have collisions, so it should not be treated as a unique identifier or a security check.

## Step 2: Make adjustment formulas safe

This fix needed more than replacing one function call because formulas such as `current * 2` still had to work. The new helper reads the formula as an expression and checks each part before calculating it.

It allows numbers, `current`, parentheses, unary signs, and the operators `+`, `-`, `*`, `/`, `//` and `%`. Function calls, attribute access, indexing and other expressions are rejected. I also added a 200-character limit, a limit on intermediate values, and a check that the final stock is a nonnegative whole number.

Checks passed for seven valid formulas and fourteen invalid or unsafe formulas. These included attempts to call functions, access attributes, divide by zero and produce invalid quantities. A rejected formula leaves the stock and audit log unchanged.

## Step 3: Remove the extra `eval()`

I replaced the last `eval()` with `print("stock audit complete")`. The message stays the same, and there are no remaining calls to `eval()` in the program.

## Step 4: Remove the password from the code

The program now reads the configured password from `WAREHOUSE_SUPERVISOR_PASSWORD`. There is no fallback password. `apply_adjustment()` raises `RuntimeError` if the variable is missing or empty, and `PermissionError` if the supplied password is incorrect. The comparison uses `hmac.compare_digest()`.

In the demo, `getpass()` asks for the password without displaying it. If no password is configured, the demo explains that the adjustment is skipped. I checked missing and empty configuration, incorrect passwords and successful authentication. Failed authentication does not change stock or create an audit entry.

## Step 5: Report stock-removal errors properly

I removed the blanket exception handler from `remove_stock()`. It now checks that the SKU is a nonempty string and the quantity is a positive integer. An unknown SKU raises `KeyError`; invalid quantities and insufficient stock raise `ValueError`.

These checks happen before changing inventory. I checked partial removal, removal of the exact available quantity, an unknown SKU, insufficient stock and invalid quantities. Rejected requests leave inventory unchanged. The demo catches the expected errors and prints an explanation instead of hiding them.

## Final check

After the fixes, I reran Bandit, Pylint and Flake8. Bandit reported no findings, so all five security findings listed above are resolved. Pylint scored the current code at **7.18/10**, and Flake8 still reported style issues. There is more cleanup to do before reaching the README's Pylint target of above 9.5; fixing these five findings does not mean the whole program is free of bugs.


## Pylint cleanup after the security fixes

After fixing the five security findings, I worked through the remaining Pylint warnings. I renamed the functions to snake_case and updated their calls, added module and function docstrings, removed the unused import and variable, and fixed spacing and long lines. I also replaced the shared history-list default with `None`, used an f-string for history entries, and kept Boolean values out of numeric quantity checks.

File operations now use `with open(...)` and an explicit UTF-8 encoding. Loading stock updates the existing dictionary instead of using a `global` statement. The report and reorder functions now loop through dictionary items directly.

The earlier 7.18/10 score above records the stage before this cleanup. The latest run scored **10.00/10 in Pylint**, with no warnings suppressed. Flake8 and Bandit also passed with no findings. I checked stock operations, history recording, JSON saving and loading, authentication, unsafe formulas and the complete demo after the changes. The updated results are saved in the three report files.
