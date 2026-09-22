import unittest
from datetime import date
from invoicer.models import Invoice, LineItem
from invoicer.report import monthly_totals as m

def inv(y, mo, amount): return Invoice("X", "c", date(y, mo, 15), [LineItem("i", amount, 1)])

class T8(unittest.TestCase):
    def test_years_separated(self):
        self.assertEqual(m([inv(2025, 9, 1000), inv(2026, 9, 2000)]), {"2025-09": 1100, "2026-09": 2200})
    def test_key_format(self):
        self.assertEqual(list(m([inv(2026, 3, 1000)])), ["2026-03"])
    def test_ordered(self):
        self.assertEqual(list(m([inv(2026, 9, 1000), inv(2025, 12, 1000), inv(2026, 1, 1000)])), ["2025-12", "2026-01", "2026-09"])
    def test_vat_included(self):
        self.assertEqual(m([inv(2026, 9, 1000), inv(2026, 9, 3000)]), {"2026-09": 4400})
    def test_empty(self):
        self.assertEqual(m([]), {})
