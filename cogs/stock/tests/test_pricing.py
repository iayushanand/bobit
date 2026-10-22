"""Phase 1 unit tests: pure pricing formulas with fixed inputs.

Run with stdlib only (no pytest on this project yet):
    python -m unittest cogs.stock.tests.test_pricing -v
"""

import math
import unittest

from cogs.stock.config import StockConfig
from cogs.stock.pricing import (
    apply_return_to_price,
    baseline_return,
    clamp_return,
    combine_returns,
    holder_aggregate_score,
    inactivity_decay_return,
    normalize_score,
    owner_activity_return,
    quote_trade,
    trade_impact_return,
)


class TestActivityScoring(unittest.TestCase):
    def test_no_activity_scores_zero(self):
        self.assertEqual(normalize_score(0, 10), 0.0)
        self.assertEqual(holder_aggregate_score([], 5, 20), 0.0)

    def test_activity_saturates_at_cap(self):
        self.assertEqual(normalize_score(10, 10), 1.0)
        self.assertEqual(normalize_score(999, 10), 1.0)
        self.assertAlmostEqual(normalize_score(5, 10), 0.5)

    def test_holder_per_member_cap_limits_whale(self):
        cfg = StockConfig()
        # One spammer with 1000 msgs counts as capped 5, not 1000.
        one_whale = holder_aggregate_score([1000], cfg.holder_per_member_cap, cfg.holder_activity_target)
        five_normal = holder_aggregate_score([5, 5, 5, 5, 5], cfg.holder_per_member_cap, cfg.holder_activity_target)
        self.assertLess(one_whale, five_normal)
        self.assertLessEqual(one_whale, 1.0)

    def test_holder_crowd_cannot_grow_unbounded(self):
        cfg = StockConfig()
        crowd = holder_aggregate_score([5] * 1000, cfg.holder_per_member_cap, cfg.holder_activity_target)
        self.assertEqual(crowd, 1.0)


class TestOwnerHolderSignals(unittest.TestCase):
    def test_owner_weight_exceeds_holder(self):
        cfg = StockConfig()
        self.assertLess(cfg.holder_max_return, cfg.owner_max_return)
        owner = owner_activity_return(1.0, 0.0, cfg.owner_max_return, cfg.stale_horizon_hours)
        holder = owner_activity_return(1.0, 0.0, cfg.holder_max_return, cfg.stale_horizon_hours)
        self.assertGreater(owner, holder)
        self.assertAlmostEqual(owner, 0.001)
        self.assertAlmostEqual(holder, 0.0004)

    def test_owner_inactivity_fades_to_small_negative_no_crash(self):
        cfg = StockConfig()
        stale = owner_activity_return(0.0, 1_000.0, cfg.owner_max_return, cfg.stale_horizon_hours)
        self.assertGreaterEqual(stale, -cfg.owner_max_return)
        self.assertLess(stale, 0.0)
        # Never a crash: bounded at a tenth of max even with zero score.
        self.assertAlmostEqual(stale, -0.0001)

    def test_signals_bounded(self):
        cfg = StockConfig()
        for score in (0.0, 0.5, 1.0):
            for hours in (0.0, 12.0, 48.0, 500.0):
                r = owner_activity_return(score, hours, cfg.owner_max_return, cfg.stale_horizon_hours)
                self.assertGreaterEqual(r, -cfg.owner_max_return)
                self.assertLessEqual(r, cfg.owner_max_return)


class TestTradeImpact(unittest.TestCase):
    def test_small_buy_small_positive(self):
        cfg = StockConfig()
        impact = trade_impact_return(1_000, 100_000, cfg.trade_sensitivity,
                                     cfg.minimum_liquidity_minor, cfg.max_trade_move)
        self.assertGreater(impact, 0.0)
        self.assertLess(impact, 0.005)

    def test_larger_buy_greater_impact(self):
        cfg = StockConfig()
        small = trade_impact_return(1_000, 100_000, cfg.trade_sensitivity,
                                    cfg.minimum_liquidity_minor, cfg.max_trade_move)
        large = trade_impact_return(50_000, 100_000, cfg.trade_sensitivity,
                                    cfg.minimum_liquidity_minor, cfg.max_trade_move)
        self.assertGreater(large, small)

    def test_sell_negative(self):
        cfg = StockConfig()
        impact = trade_impact_return(-10_000, 100_000, cfg.trade_sensitivity,
                                     cfg.minimum_liquidity_minor, cfg.max_trade_move)
        self.assertLess(impact, 0.0)

    def test_trade_capped(self):
        cfg = StockConfig()
        whale = trade_impact_return(100_000_000, 100_000, cfg.trade_sensitivity,
                                    cfg.minimum_liquidity_minor, cfg.max_trade_move)
        self.assertAlmostEqual(whale, cfg.max_trade_move)

    def test_minimum_liquidity_floor(self):
        cfg = StockConfig()
        impact = trade_impact_return(10_000, 1, cfg.trade_sensitivity,
                                     cfg.minimum_liquidity_minor, cfg.max_trade_move)
        self.assertLessEqual(abs(impact), cfg.max_trade_move)


class TestCombineAndBounds(unittest.TestCase):
    def test_quiet_stock_small_decay(self):
        cfg = StockConfig()
        decay = inactivity_decay_return(600, cfg.inactivity_decay_per_day)  # 10 min
        self.assertLess(decay, 0.0)
        self.assertGreater(decay, -0.001)  # tiny, not a collapse
        out = combine_returns(10_000, 0.0, 0.0, decay, 0.0, 0.0,
                              cfg.max_scheduled_move, cfg.min_price_minor, cfg.max_price_minor)
        self.assertLess(out.new_price_minor, 10_000)
        self.assertGreater(out.new_price_minor, 9_900)

    def test_per_update_cap_respected(self):
        cfg = StockConfig()
        out = combine_returns(10_000, 0.05, 0.05, 0.0, 0.05, 0.05,
                              cfg.max_scheduled_move, cfg.min_price_minor, cfg.max_price_minor)
        self.assertAlmostEqual(out.clamped_return, cfg.max_scheduled_move)
        self.assertEqual(out.new_price_minor, 10_100)

    def test_price_floor_and_ceiling(self):
        cfg = StockConfig()
        low = apply_return_to_price(150, -0.99, cfg.min_price_minor, cfg.max_price_minor)
        self.assertEqual(low, cfg.min_price_minor)
        high = apply_return_to_price(cfg.max_price_minor - 10, 0.99,
                                     cfg.min_price_minor, cfg.max_price_minor)
        self.assertEqual(high, cfg.max_price_minor)
        with self.assertRaises(ValueError):
            apply_return_to_price(100, math.nan, cfg.min_price_minor, cfg.max_price_minor)
        with self.assertRaises(ValueError):
            apply_return_to_price(100, math.inf, cfg.min_price_minor, cfg.max_price_minor)

    def test_elapsed_time_independent_of_tick_count(self):
        # exp() is time-based: a single 24h decay vs compounded 10-min
        # steps must stay close (no repeated fixed-fall per tick).
        cfg = StockConfig()
        one = inactivity_decay_return(86_400, cfg.inactivity_decay_per_day)
        price_one = apply_return_to_price(100_000, one, cfg.min_price_minor, cfg.max_price_minor)
        price_many = 100_000
        for _ in range(144):
            step = inactivity_decay_return(600, cfg.inactivity_decay_per_day)
            price_many = apply_return_to_price(price_many, step, cfg.min_price_minor, cfg.max_price_minor)
        self.assertLess(abs(price_one - price_many), 100)  # within ~0.1%

    def test_baseline_deterministic_and_bounded(self):
        cfg = StockConfig()
        self.assertAlmostEqual(baseline_return(1.0, cfg.baseline_vol), cfg.baseline_vol)
        self.assertAlmostEqual(baseline_return(-1.0, cfg.baseline_vol), -cfg.baseline_vol)
        with self.assertRaises(ValueError):
            baseline_return(2.0, cfg.baseline_vol)


class TestQuoteAndFees(unittest.TestCase):
    def test_buy_quote_fee_math(self):
        q = quote_trade(10, 1_000, 0.01, True)
        self.assertEqual(q.gross_minor, 10_000)
        self.assertEqual(q.fee_minor, 100)
        self.assertEqual(q.total_minor, 10_100)

    def test_sell_quote_fee_math(self):
        q = quote_trade(10, 1_000, 0.01, False)
        self.assertEqual(q.total_minor, 9_900)

    def test_invalid_quantities_rejected(self):
        with self.assertRaises(ValueError):
            quote_trade(0, 1_000, 0.01, True)
        with self.assertRaises(ValueError):
            quote_trade(-5, 1_000, 0.01, True)
        with self.assertRaises(ValueError):
            quote_trade(5, 0, 0.01, True)

    def test_clamp_helper(self):
        self.assertEqual(clamp_return(0.5, 0.01), 0.01)
        self.assertEqual(clamp_return(-0.5, 0.01), -0.01)
        self.assertEqual(clamp_return(0.005, 0.01), 0.005)


class TestConfigValidation(unittest.TestCase):
    def test_holder_must_be_less_than_owner(self):
        with self.assertRaises(ValueError):
            StockConfig(holder_max_return=0.01, owner_max_return=0.001)

    def test_fee_bounded(self):
        with self.assertRaises(ValueError):
            StockConfig(trading_fee_rate=0.5)


if __name__ == "__main__":
    unittest.main()
