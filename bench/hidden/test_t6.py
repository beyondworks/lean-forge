import unittest
from datetime import date
from invoicer.models import Invoice
from invoicer.terms import due_date

def d(y, m, dd): return due_date(Invoice("X", "c", date(y, m, dd)))

class T6(unittest.TestCase):
    def test_weekday(self): self.assertEqual(d(2026, 9, 1), date(2026, 10, 1))
    def test_lands_saturday(self): self.assertEqual(d(2026, 9, 3), date(2026, 10, 5))
    def test_lands_sunday(self): self.assertEqual(d(2026, 9, 4), date(2026, 10, 5))
    def test_issued_saturday_lands_monday(self): self.assertEqual(d(2026, 9, 5), date(2026, 10, 5))
    def test_month_end(self): self.assertEqual(d(2026, 1, 31), date(2026, 3, 2))
