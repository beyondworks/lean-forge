import unittest, pathlib
class T3(unittest.TestCase):
    def test_typo(self):
        s = pathlib.Path("invoicer/calc.py").read_text()
        self.assertIn("Callers receive plain ints", s)
        self.assertNotIn("recieve", s)
