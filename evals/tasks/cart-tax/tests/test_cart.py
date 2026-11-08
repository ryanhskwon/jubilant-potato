import unittest
from cart import Cart
from pricing import add_tax, apply_discount


class T(unittest.TestCase):
    def test_discount(self):
        self.assertAlmostEqual(apply_discount(200, 10), 180)

    def test_tax(self):
        self.assertEqual(add_tax(100, 0.1), 110.0)
        self.assertEqual(add_tax(19.99, 0.08), 21.59)

    def test_total(self):
        c = Cart(discount_percent=10)
        c.add(50, 2)
        c.add(100)
        self.assertEqual(c.total(), 198.0)  # 200 → 할인 180 → 세금 198

    def test_no_discount(self):
        c = Cart()
        c.add(10)
        self.assertEqual(c.total(), 11.0)


if __name__ == "__main__":
    unittest.main()
