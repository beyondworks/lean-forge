from .calc import total


def monthly_totals(invoices):
    """Sales per month."""
    out = {}
    for inv in invoices:
        out[inv.issued.month] = out.get(inv.issued.month, 0) + total(inv)
    return out
