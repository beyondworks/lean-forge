import unittest
from datetime import date
from invoicer.numbering import next_invoice_id as n

class T4(unittest.TestCase):
    def test_first_of_year(self):
        self.assertEqual(n([], date(2026, 3, 1)), "INV-2026-0001")
    def test_increment(self):
        self.assertEqual(n(["INV-2026-0001", "INV-2026-0002"], date(2026, 3, 1)), "INV-2026-0003")
    def test_yearly_reset(self):
        self.assertEqual(n(["INV-2025-0041"], date(2026, 1, 2)), "INV-2026-0001")
    def test_max_plus_one_not_fill_gap(self):
        self.assertEqual(n(["INV-2026-0001", "INV-2026-0005"], date(2026, 6, 1)), "INV-2026-0006")
    def test_ignore_legacy(self):
        self.assertEqual(n(["A-1", "B-2", "INV-2026-0007"], date(2026, 6, 1)), "INV-2026-0008")
