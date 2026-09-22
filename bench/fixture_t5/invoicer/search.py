def find_by_customer(invoices, name):
    """Return invoices whose customer matches name."""
    return [i for i in invoices if i.customer == name]
