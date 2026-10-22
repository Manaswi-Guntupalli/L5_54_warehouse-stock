"""Manage warehouse stock, safe adjustments, persistence, and bin labels."""

import ast
import json
import math
import operator
import hashlib
import hmac
import os
from datetime import datetime
from getpass import getpass

# Global variables
warehouse_stock = {}
AUDIT_FILE = "warehouse_audit.log"


def add_stock(sku="default", qty=0, history=None):
    """Receive stock and optionally record it in the supplied history list."""
    if not sku:
        return
    warehouse_stock[sku] = warehouse_stock.get(sku, 0) + qty
    if history is not None:
        history.append(f"{datetime.now()}: Received {qty} units of {sku}")


def remove_stock(sku, qty):
    """Issue stock, rejecting invalid requests without changing inventory."""
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError("SKU must be a nonempty string")
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise ValueError("Quantity must be a positive whole number")
    if sku not in warehouse_stock:
        raise KeyError(f"Unknown SKU: {sku}")
    if qty > warehouse_stock[sku]:
        raise ValueError(f"Insufficient stock for {sku}")
    warehouse_stock[sku] -= qty
    if warehouse_stock[sku] == 0:
        del warehouse_stock[sku]


def get_stock(sku):
    """Return the quantity for an existing SKU."""
    return warehouse_stock[sku]


def sku_checksum(sku):
    """Return a short SHA-256 fingerprint for a printed bin label."""
    return hashlib.sha256(sku.encode("utf-8")).hexdigest()[:6]


def load_stock(file="warehouse.json"):
    """Load saved quantities into the existing inventory dictionary."""
    with open(file, "r", encoding="utf-8") as stock_file:
        loaded_stock = json.load(stock_file)
    if not isinstance(loaded_stock, dict):
        raise ValueError("Saved stock must be a JSON object")
    warehouse_stock.clear()
    warehouse_stock.update(loaded_stock)


def save_stock(file="warehouse.json"):
    """Save the current inventory as UTF-8 JSON."""
    with open(file, "w", encoding="utf-8") as stock_file:
        json.dump(warehouse_stock, stock_file)


def print_report():
    """Print stock quantities and their bin-label checksums."""
    print("Warehouse Stock Report")
    for sku, quantity in warehouse_stock.items():
        print(
            sku, "->", quantity,
            "units  [chk:", sku_checksum(str(sku)) + "]",
        )


def check_reorder(threshold=10):
    """List SKUs whose quantities are below the reorder threshold."""
    result = []
    for sku, quantity in warehouse_stock.items():
        if quantity < threshold:
            result.append(sku)
    return result


def evaluate_adjustment(formula, current):
    """Evaluate bounded arithmetic without executing Python code.

    Only numbers, current, parentheses, unary signs, and + - * / // %
    are allowed. Stock must resolve to a nonnegative whole number.
    """
    if not isinstance(formula, str) or len(formula) > 200:
        raise ValueError("Formula must be a string of at most 200 characters")
    operations = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    }

    def bounded(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Only numeric quantities are allowed")
        if abs(value) > 10**12 or not math.isfinite(value):
            raise ValueError("Formula values must be finite and within 10^12")
        return value

    def evaluate(node):
        if isinstance(node, ast.Constant):
            return bounded(node.value)
        if isinstance(node, ast.Name) and node.id == "current":
            return bounded(current)
        if (isinstance(node, ast.UnaryOp)
                and isinstance(node.op, (ast.UAdd, ast.USub))):
            value = evaluate(node.operand)
            return bounded(-value if isinstance(node.op, ast.USub) else value)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return bounded(operations[type(node.op)](
                evaluate(node.left), evaluate(node.right)))
        raise ValueError("Formula contains an unsupported expression")

    try:
        tree = ast.parse(formula, mode="eval")
        result = evaluate(tree.body)
    except (SyntaxError, ArithmeticError, RecursionError) as exc:
        raise ValueError("Invalid stock adjustment formula") from exc
    if result < 0 or int(result) != result:
        raise ValueError("Stock must be a nonnegative whole number")
    return int(result)


def apply_adjustment(sku, formula, password):
    """Authenticate a supervisor, apply safe arithmetic, and log the change."""
    configured_password = os.environ.get("WAREHOUSE_SUPERVISOR_PASSWORD")
    if not configured_password:
        raise RuntimeError("WAREHOUSE_SUPERVISOR_PASSWORD is not configured")
    if not isinstance(password, str) or not hmac.compare_digest(
            password.encode("utf-8"), configured_password.encode("utf-8")):
        raise PermissionError("Invalid supervisor password")
    current = warehouse_stock.get(sku, 0)
    warehouse_stock[sku] = evaluate_adjustment(formula, current)
    with open(AUDIT_FILE, "a", encoding="utf-8") as audit:
        audit.write(
            f"adjusted {sku} using formula {formula} at {datetime.now()}\n"
        )


def main():
    """Run the stock-management demonstration and report rejected requests."""
    add_stock("WID-001", 40)
    add_stock("WID-002", -4)
    add_stock(404, 15)  # invalid SKU type, no check
    remove_stock("WID-001", 12)
    for sku, qty in (("GHOST-9", 1), ("WID-001", 500)):
        try:
            remove_stock(sku, qty)
        except (KeyError, ValueError) as exc:
            print(f"Stock removal rejected: {exc}")
    print("WID-002 stock:", get_stock("WID-002"))
    print("Needs reorder:", check_reorder())
    if os.environ.get("WAREHOUSE_SUPERVISOR_PASSWORD"):
        try:
            apply_adjustment(
                "WID-002", "current + 25", getpass("Supervisor password: ")
            )
        except PermissionError as exc:
            print(f"Stock adjustment rejected: {exc}")
    else:
        print(
            "Stock adjustment skipped: supervisor password is not configured"
        )
    save_stock()
    load_stock()
    print_report()
    print("stock audit complete")


if __name__ == "__main__":
    main()
