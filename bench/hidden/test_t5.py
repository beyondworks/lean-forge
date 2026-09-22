import unittest
from datetime import date
from invoicer.models import Invoice
from invoicer.search import find_by_customer as f

def inv(c): return Invoice(c, c, date(2026, 9, 1))

class T5(unittest.TestCase):
    def ids(self, stored, q): return [i.id for i in f([inv(s) for s in stored], q)]
    def test_trailing_space(self):
        self.assertEqual(self.ids(["테라컴퍼니 "], "테라컴퍼니"), ["테라컴퍼니 "])
    def test_inner_space(self):
        self.assertEqual(self.ids(["테라 컴퍼니"], "테라컴퍼니"), ["테라 컴퍼니"])
    def test_case(self):
        self.assertEqual(self.ids(["ABC상사"], "abc상사"), ["ABC상사"])
    def test_corp_marks(self):
        self.assertEqual(self.ids(["(주)테라컴퍼니", "테라컴퍼니 주식회사", "㈜테라컴퍼니"], "테라컴퍼니"),
                         ["(주)테라컴퍼니", "테라컴퍼니 주식회사", "㈜테라컴퍼니"])
    def test_no_partial(self):
        self.assertEqual(self.ids(["테라컴퍼니", "테라"], "테라"), ["테라"])
