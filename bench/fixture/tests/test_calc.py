import unittest
from datetime import date

from invoicer.models import Invoice, LineItem
from invoicer.calc import subtotal, discounted, tax, total


class CalcTest(unittest.TestCase):
    def test_simple_invoice(self):
        inv = Invoice("A-1", "테라컴퍼니", date(2026, 9, 1), [LineItem("컨설팅", 1000, 2)])
        self.assertEqual(subtotal(inv), 2000)
        self.assertEqual(discounted(inv), 2000)
        self.assertEqual(tax(inv), 200)
        self.assertEqual(total(inv), 2200)


if __name__ == "__main__":
    unittest.main()
