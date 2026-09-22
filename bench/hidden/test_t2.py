import unittest
from datetime import date
from invoicer.models import Invoice, LineItem
from invoicer.calc import subtotal, discounted, tax, total

def inv(items, rate=0.0):
    return Invoice("X", "c", date(2026, 9, 1), [LineItem("i", p, q) for p, q in items], rate)

class T2(unittest.TestCase):
    def test_discount_on_subtotal(self):
        i = inv([(3333, 1)] * 3, 0.1)
        self.assertEqual(subtotal(i), 9999)
        self.assertEqual(discounted(i), 8999)
        self.assertEqual(tax(i), 900)
        self.assertEqual(total(i), 9899)
    def test_half_up_tax_15(self):
        self.assertEqual(total(inv([(15, 1)])), 17)
    def test_half_up_tax_25(self):
        self.assertEqual(tax(inv([(25, 1)])), 3)
        self.assertEqual(total(inv([(25, 1)])), 28)
    def test_clean_discount(self):
        i = inv([(1000, 7)], 0.15)
        self.assertEqual((discounted(i), tax(i), total(i)), (5950, 595, 6545))
    def test_half_up_discount(self):
        i = inv([(105, 1)], 0.1)  # discount 10.5 -> 11
        self.assertEqual(discounted(i), 94)
        self.assertEqual(total(i), 103)  # 94 + 9.4 -> 9
