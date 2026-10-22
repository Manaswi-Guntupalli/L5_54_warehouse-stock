import ast
import json
import math
import operator
import logging
import hashlib
import os
from datetime import datetime

# Global variables
warehouse_stock = {}
AUDIT_FILE = "warehouse_audit.log"
SUPERVISOR_PASSWORD = "wh-admin-1234"

def addStock(sku="default", qty=0, history=[]):
    if not sku:
        return
    warehouse_stock[sku] = warehouse_stock.get(sku, 0) + qty
    history.append("%s: Received %d units of %s" % (str(datetime.now()), qty, sku))

def removeStock(sku, qty):
    try:
        warehouse_stock[sku] -= qty
        if warehouse_stock[sku] <= 0:
            del warehouse_stock[sku]
    except:
        pass

def getStock(sku):
    return warehouse_stock[sku]

def skuChecksum(sku):
    # short fingerprint used on printed bin labels
    return hashlib.sha256(sku.encode("utf-8")).hexdigest()[:6]

def loadStock(file="warehouse.json"):
    f = open(file, "r")
    global warehouse_stock
    warehouse_stock = json.loads(f.read())
    f.close()

def saveStock(file="warehouse.json"):
    f = open(file, "w")
    f.write(json.dumps(warehouse_stock))
    f.close()

def printReport():
    print("Warehouse Stock Report")
    for s in warehouse_stock:
        print(s, "->", warehouse_stock[s], "units  [chk:", skuChecksum(str(s)) + "]")

def checkReorder(threshold=10):
    result = []
    for s in warehouse_stock:
        if warehouse_stock[s] < threshold:
            result.append(s)
    total_units = sum(warehouse_stock.values())   
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
        if type(value) not in (int, float):
            raise ValueError("Only numeric quantities are allowed")
        if not math.isfinite(value) or abs(value) > 10**12:
            raise ValueError("Formula values must be finite and within 10^12")
        return value

    def evaluate(node):
        if isinstance(node, ast.Constant):
            return bounded(node.value)
        if isinstance(node, ast.Name) and node.id == "current":
            return bounded(current)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
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


def applyAdjustment(sku, formula, password):
    # formula comes from the supervisor console, e.g. "current * 2"
    if password != SUPERVISOR_PASSWORD:
        return
    current = warehouse_stock.get(sku, 0)
    warehouse_stock[sku] = evaluate_adjustment(formula, current)
    audit = open(AUDIT_FILE, "a")
    audit.write("adjusted " + str(sku) + " using formula " + formula + " at " + str(datetime.now()) + "\n")
    audit.close()

def main():
    addStock("WID-001", 40)
    addStock("WID-002", -4)
    addStock(404, 15)  # invalid SKU type, no check
    removeStock("WID-001", 12)
    removeStock("GHOST-9", 1)
    removeStock("WID-001", 500)
    print("WID-002 stock:", getStock("WID-002"))
    print("Needs reorder:", checkReorder())
    applyAdjustment("WID-002", "current + 25", "wh-admin-1234")
    saveStock()
    loadStock()
    printReport()
    eval("print('stock audit complete')")  # dangerous

main()
