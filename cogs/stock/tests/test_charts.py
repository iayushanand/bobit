"""Chart + statistics tests (matplotlib optional — skip if missing)."""

import io
import unittest

from cogs.stock.statistics import allocation, candles, movers, price_series, side_volumes, summarize, volumes_per_interval

try:
    from cogs.stock.charts import DOWN_COLOR, UP_COLOR, movement_colors, use_candles
    CHARTS_TESTABLE = True
except ImportError:
    CHARTS_TESTABLE = False


class TestUseCandles(unittest.TestCase):
    def test_threshold(self):
        self.assertFalse(use_candles(0))
        self.assertFalse(use_candles(7))
        self.assertFalse(use_candles(11))
        self.assertTrue(use_candles(12))
        self.assertTrue(use_candles(200))


class TestMovementColors(unittest.TestCase):
    def setUp(self):
        if not CHARTS_TESTABLE:
            self.skipTest("matplotlib not installed")

    def test_all_up_green(self):
        self.assertEqual(movement_colors([100.0, 101.0, 105.0]), [UP_COLOR, UP_COLOR])

    def test_all_down_red(self):
        self.assertEqual(movement_colors([105.0, 101.0, 100.0]), [DOWN_COLOR, DOWN_COLOR])

    def test_mixed_has_both(self):
        colors = movement_colors([100.0, 110.0, 105.0, 107.0])
        self.assertIn(UP_COLOR, colors)
        self.assertIn(DOWN_COLOR, colors)
        self.assertEqual(len(colors), 3)

    def test_flat_counts_as_up(self):
        self.assertEqual(movement_colors([100.0, 100.0]), [UP_COLOR])

    def test_empty_and_single_have_no_segments(self):
        self.assertEqual(movement_colors([]), [])
        self.assertEqual(movement_colors([100.0]), [])


class TestStatistics(unittest.TestCase):
    def test_summarize_empty_and_single(self):
        s = summarize([])
        self.assertEqual(s["points"], 0)
        s1 = summarize([{"ts": 1, "price": 1000}])
        self.assertEqual(s1["points"], 1)
        self.assertEqual(s1["change"], 0)

    def test_price_series_sorted(self):
        ts, prices = price_series([{"ts": 3, "price": 30}, {"ts": 1, "price": 10}])
        self.assertEqual(list(ts), [1, 3])

    def test_allocation_groups_other(self):
        positions = [{"ticker": f"S{i}", "name": "", "quantity": 1, "price": 1, "value": 10 - i}
                     for i in range(8)]
        out = allocation(positions, top_n=5)
        self.assertEqual(len(out), 6)
        self.assertEqual(out[-1]["ticker"], "Other")

    def test_movers(self):
        stocks = [{"_id": "a", "ticker": "A", "current_price": 100},
                  {"_id": "b", "ticker": "B", "current_price": 100}]
        hist = {"a": [{"ts": 1, "price": 100}, {"ts": 2, "price": 120}],
                "b": [{"ts": 1, "price": 100}, {"ts": 2, "price": 80}]}
        gainers, losers = movers(stocks, hist)
        self.assertEqual(gainers[0]["ticker"], "A")
        self.assertEqual(losers[0]["ticker"], "B")


class TestVolumesPerInterval(unittest.TestCase):
    def test_buckets_trades_to_latest_point(self):
        vols = volumes_per_interval(
            [100.0, 200.0, 300.0],
            [{"ts": 110, "quantity": 5}, {"ts": 250, "quantity": 3},
             {"ts": 50, "quantity": 2}, {"ts": 300, "quantity": 7}])
        self.assertEqual(vols, [7.0, 3.0, 7.0])

    def test_empty_inputs(self):
        self.assertEqual(volumes_per_interval([], [{"ts": 1, "quantity": 5}]), [])
        self.assertEqual(volumes_per_interval([1.0, 2.0], []), [0.0, 0.0])


class TestCandles(unittest.TestCase):
    def test_empty_and_mismatched(self):
        self.assertEqual(candles([], [], []), [])
        self.assertEqual(candles([1.0], [], []), [])
        self.assertEqual(candles([1.0], [100.0, 200.0], []), [])

    def test_single_point_is_doji(self):
        out = candles([5.0], [100.0], [3.0])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0], {"ts": 5.0, "open": 100.0, "high": 100.0,
                                  "low": 100.0, "close": 100.0, "volume": 3.0})

    def test_buckets_ohlc_and_volume(self):
        out = candles([1.0, 2.0, 3.0, 4.0], [100.0, 110.0, 105.0, 90.0],
                      [1.0, 2.0, 3.0, 4.0], max_candles=2)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["open"], 100.0)
        self.assertEqual(out[0]["close"], 110.0)
        self.assertEqual(out[0]["high"], 110.0)
        self.assertEqual(out[0]["low"], 100.0)
        self.assertEqual(out[0]["volume"], 3.0)
        self.assertEqual(out[1], {"ts": 4.0, "open": 105.0, "high": 105.0,
                                  "low": 90.0, "close": 90.0, "volume": 7.0})

    def test_caps_candle_count(self):
        out = candles([float(i) for i in range(100)], [float(i) for i in range(100)],
                      max_candles=30)
        self.assertLessEqual(len(out), 30)
        self.assertGreater(len(out), 0)


class TestSideVolumes(unittest.TestCase):
    def test_splits_buys_and_sells(self):
        buys, sells = side_volumes(
            [100.0, 200.0, 300.0, 400.0],
            [{"ts": 110, "quantity": 5, "side": "buy"},
             {"ts": 150, "quantity": 2, "side": "sell"},
             {"ts": 350, "quantity": 7, "side": "sell"}],
            max_candles=2)
        self.assertEqual(buys, [5.0, 0.0])
        self.assertEqual(sells, [2.0, 7.0])

    def test_aligned_with_candles(self):
        ts = [float(i) for i in range(10)]
        px = [100.0 + i for i in range(10)]
        trades = [{"ts": float(i), "quantity": 1, "side": "buy"} for i in range(10)]
        out = candles(ts, px, max_candles=3)
        buys, sells = side_volumes(ts, trades, max_candles=3)
        self.assertEqual(len(buys), len(out))
        self.assertEqual(len(sells), len(out))
        self.assertEqual(sum(buys), 10.0)

    def test_empty(self):
        self.assertEqual(side_volumes([], []), ([], []))
        self.assertEqual(side_volumes([1.0], []), ([0.0], [0.0]))


class TestCharts(unittest.TestCase):
    def test_render_png(self):
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            self.skipTest("matplotlib not installed")
            return
        from cogs.stock.charts import allocation_chart, movers_chart, price_chart
        buy_sell = [{"ts": 1, "quantity": 5, "side": "buy"},
                    {"ts": 2, "quantity": 2, "side": "sell"}]
        busy = [{"ts": float(t), "quantity": (t % 4) + 1,
                 "side": "sell" if t % 3 == 0 else "buy"} for t in range(40)]
        for buf in (price_chart([1, 2, 3], [100, 110, 105], "BIT"),
                    price_chart([1, 2, 3], [100, 110, 105], "BIT", "₹", buy_sell),
                    price_chart([1, 2, 3], [100, 110, 105], "BIT", "₹", []),
                    # sparse-new-stock shape (7 pts): line mode, no flat dashes
                    price_chart([float(t) for t in range(7)],
                                [10000, 10001, 10007, 10009, 10008, 10009, 10012],
                                "AYU", "₹", [{"ts": 1, "quantity": 10, "side": "buy"},
                                             {"ts": 2, "quantity": 50, "side": "buy"},
                                             {"ts": 3, "quantity": 20, "side": "sell"}]),
                    # dense history: candlestick + buy/sell panel
                    price_chart([float(t) for t in range(40)],
                                [10000 + ((t * 37) % 200) - 100 for t in range(40)],
                                "AYU", "₹", busy),
                    price_chart([], [], "BIT"),
                    price_chart([1], [100], "BIT"),
                    allocation_chart(["A", "B"], [70, 30]),
                    allocation_chart([], []),
                    movers_chart(["A", "B"], [0.05, -0.03]),
                    movers_chart([], [])):
            self.assertIsInstance(buf, io.BytesIO)
            self.assertGreater(len(buf.getvalue()), 0)
            self.assertTrue(buf.getvalue()[:8].startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
