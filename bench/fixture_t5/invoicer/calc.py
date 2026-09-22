"""Invoice arithmetic. All amounts are integer won.

Callers recieve plain ints so they can be printed or stored directly.
"""

TAX_RATE = 0.1


def line_total(item, discount_rate=0.0):
    """Return the discounted amount for one line."""
    return int(item.unit_price * item.qty * (1 - discount_rate))


def subtotal(inv):
    """Sum of lines before discount."""
    return sum(i.unit_price * i.qty for i in inv.items)


def discounted(inv):
    """Sum of lines after discount."""
    return sum(line_total(i, inv.discount_rate) for i in inv.items)


def tax(inv):
    """VAT on the discounted amount."""
    return int(discounted(inv) * TAX_RATE)


def total(inv):
    """Amount the customer pays."""
    return discounted(inv) + tax(inv)
