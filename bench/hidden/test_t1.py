import csv, io, os, tempfile, unittest
from datetime import date
from invoicer.models import Invoice, LineItem
from invoicer.export import export_csv

class T1(unittest.TestCase):
    def setUp(self):
        self.invs = [
            Invoice("B-2", "가나상사", date(2026, 9, 15), [LineItem("개발", 250000, 4)], 0.1),
            Invoice("A-1", "테라컴퍼니", date(2026, 9, 1), [LineItem("컨설팅", 1000, 2), LineItem("출장", 30000, 1)]),
        ]
        self.path = os.path.join(tempfile.mkdtemp(), "out.csv")
        export_csv(self.invs, self.path)
        self.raw = open(self.path, "rb").read()
        self.rows = list(csv.reader(io.StringIO(self.raw.decode("utf-8-sig"))))
    def test_bom(self):
        self.assertTrue(self.raw.startswith(b"\xef\xbb\xbf"))
    def test_header(self):
        self.assertEqual(self.rows[0], ["송장번호", "고객", "발행일", "소계", "할인", "부가세", "합계"])
    def test_sorted_by_date(self):
        self.assertEqual([r[0] for r in self.rows[1:]], ["A-1", "B-2"])
    def test_values(self):
        self.assertEqual(self.rows[1], ["A-1", "테라컴퍼니", "2026-09-01", "32000", "0", "3200", "35200"])
        self.assertEqual(self.rows[2], ["B-2", "가나상사", "2026-09-15", "1000000", "100000", "90000", "990000"])
    def test_row_count(self):
        self.assertEqual(len(self.rows), 3)
