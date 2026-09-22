import unittest
from invoicer.words import amount_in_korean as k

class T7(unittest.TestCase):
    def test_basic(self): self.assertEqual(k(123000), "금 일십이만삼천원정")
    def test_ten_thousand(self): self.assertEqual(k(10000), "금 일만원정")
    def test_ones_written(self): self.assertEqual(k(110), "금 일백일십원정")
    def test_eok(self): self.assertEqual(k(105000000), "금 일억오백만원정")
    def test_zero_rejected(self):
        with self.assertRaises(ValueError): k(0)
