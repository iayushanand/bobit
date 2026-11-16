"""Unit tests for the slabbed fixed deposit math.

Run with stdlib only:
    python -m unittest cogs.stock.tests.test_slabbed_fixed_deposit -v
"""

import unittest

from cogs.stock.slabbed_fixed_deposit import (
    SLAB_RATES,
    TENURES,
    slab_interest,
    tenure_multiplier,
)

MEDIAN = 100_000


class TestSlabInterest(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(slab_interest(0, MEDIAN), 0)

    def test_first_slab(self):
        self.assertAlmostEqual(slab_interest(50_000, MEDIAN), 5_000)

    def test_on_slab_edge(self):
        self.assertAlmostEqual(slab_interest(100_000, MEDIAN), 9_000)

    def test_across_slabs(self):
        self.assertAlmostEqual(slab_interest(300_000, MEDIAN), 19_000)

    def test_top_slab(self):
        self.assertAlmostEqual(slab_interest(1_000_000, MEDIAN), 35_000)

    def test_no_cliff_at_edges(self):
        for edge in (50_000, 100_000, 200_000, 400_000):
            with self.subTest(edge=edge):
                self.assertGreater(slab_interest(edge + 1, MEDIAN), slab_interest(edge, MEDIAN))

    def test_always_increasing(self):
        values = [slab_interest(a, MEDIAN) for a in range(0, 1_000_001, 10_000)]
        for lower, higher in zip(values, values[1:]):
            self.assertLess(lower, higher)

    def test_rate_falls_for_big_deposits(self):
        small = slab_interest(50_000, MEDIAN) / 50_000
        big = slab_interest(1_000_000, MEDIAN) / 1_000_000
        self.assertGreater(small, big)

    def test_never_above_top_rate(self):
        for amount in (1, 50_000, 300_000, 10_000_000):
            with self.subTest(amount=amount):
                self.assertLessEqual(slab_interest(amount, MEDIAN), SLAB_RATES[0] * amount)

    def test_scales_with_median(self):
        self.assertAlmostEqual(slab_interest(600_000, 2 * MEDIAN), 2 * slab_interest(300_000, MEDIAN))


class TestTenureMultiplier(unittest.TestCase):
    def test_under_one_day(self):
        self.assertEqual(tenure_multiplier(0), 0.0)
        self.assertEqual(tenure_multiplier(0.9), 0.0)

    def test_exact_tenures(self):
        for days, mult in TENURES.items():
            with self.subTest(days=days):
                self.assertEqual(tenure_multiplier(days), mult)

    def test_between_tenures(self):
        self.assertEqual(tenure_multiplier(8), TENURES[7])
        self.assertEqual(tenure_multiplier(29.9), TENURES[14])

    def test_past_longest(self):
        self.assertEqual(tenure_multiplier(100), TENURES[30])

    def test_never_decreases(self):
        values = [tenure_multiplier(d / 2) for d in range(0, 80)]
        for lower, higher in zip(values, values[1:]):
            self.assertLessEqual(lower, higher)


if __name__ == "__main__":
    unittest.main()
