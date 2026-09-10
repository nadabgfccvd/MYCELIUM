from __future__ import annotations

import unittest

from mycelium_accel.prime import is_prime, next_prime, require_prime


class PrimeTests(unittest.TestCase):
    def test_is_prime(self) -> None:
        self.assertTrue(is_prime(101))
        self.assertTrue(is_prime(2))
        self.assertFalse(is_prime(1))
        self.assertFalse(is_prime(100))

    def test_next_prime(self) -> None:
        self.assertEqual(next_prime(100), 101)
        self.assertEqual(next_prime(101), 101)

    def test_require_prime(self) -> None:
        self.assertEqual(require_prime(103), 103)
        with self.assertRaises(ValueError):
            require_prime(102)


if __name__ == "__main__":
    unittest.main()
