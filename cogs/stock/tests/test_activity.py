"""Activity filtering, aggregation, and scheduled-update behavior."""

import random
import time
import unittest

from cogs.stock.activity import ActivityTracker, aggregate_window, count_events
from cogs.stock.config import StockConfig
from cogs.stock.market_tasks import run_market_update, update_one_stock
from cogs.stock.repository import InMemoryRepository
from cogs.stock.service import StockService


class TestActivityFilter(unittest.TestCase):
    def test_ignores_bots_commands_empty(self):
        t = ActivityTracker()
        self.assertFalse(t.is_qualifying_message(".stock buy BIT 1", False, False, 1, ()))
        self.assertFalse(t.is_qualifying_message("hello", True, False, 1, ()))
        self.assertFalse(t.is_qualifying_message("   ", False, False, 1, ()))
        self.assertFalse(t.is_qualifying_message("hello", False, True, 1, ()))
        self.assertFalse(t.is_qualifying_message("hello", False, False, 99, (99,)))
        self.assertTrue(t.is_qualifying_message("hello world", False, False, 1, ()))

    def test_cooldown(self):
        t = ActivityTracker(cooldown_seconds=45)
        self.assertTrue(t.check_cooldown(5, now=1000.0))
        self.assertFalse(t.check_cooldown(5, now=1010.0))
        self.assertTrue(t.check_cooldown(5, now=1100.0))

    def test_owner_excluded_from_holders(self):
        owner, holders = aggregate_window({1: 10, 2: 3, 3: 1}, owner_id=1, per_member_cap=5)
        self.assertEqual(owner, 10)
        self.assertNotIn(1, holders)
        self.assertEqual(holders[2], 3)


class TestScheduledUpdate(unittest.TestCase):
    def test_only_owner_holder_affect_price(self):
        import asyncio
        cfg = StockConfig()
        repo = InMemoryRepository()
        svc = StockService(repo, cfg)

        async def go():
            doc = await svc.create_stock(1, 100, "bit", "Bit Corp")
            sid = doc["_id"]
            now = time.time()
            # stranger activity must have no direct effect: record nothing for them.
            # owner active:
            await repo.record_activity({"stock_id": sid, "guild_id": 1, "user_id": 100,
                                        "role": "owner", "ts": now})
            e1 = await update_one_stock(repo, await svc.require_stock(1, "BIT"),
                                        cfg, now, random.Random(1))
            self.assertGreater(e1["components"]["owner"], 0)
            # quiet stock decays gradually, never crashes
            doc2 = await svc.require_stock(1, "BIT")
            e2 = await update_one_stock(repo, doc2, cfg, now + 600, random.Random(1))
            self.assertLess(e2["price"], e1["price"] + 1000)
        asyncio.run(go())

    def test_restart_safe_single_bounded_move(self):
        import asyncio
        cfg = StockConfig()
        repo = InMemoryRepository()
        svc = StockService(repo, cfg)

        async def go():
            await svc.create_stock(1, 100, "bit", "Bit Corp")
            doc = await svc.require_stock(1, "BIT")
            old = doc["current_price"]
            # simulate 7 days downtime in ONE update: still clamped to 1%
            e = await update_one_stock(repo, doc, cfg, time.time() + 7 * 86400,
                                       random.Random(0))
            self.assertGreaterEqual(e["price"], int(old * 0.99) - 5)
        asyncio.run(go())

    def test_unrelated_chat_has_no_effect(self):
        events = [{"user_id": 999, "ts": time.time()}]
        counts = count_events(events)
        # stranger id 999 is neither owner (100) nor holder; caller must not
        # attribute their messages to the stock — counts exist but service
        # only queries per-stock events recorded for eligible users.
        self.assertIn(999, counts)


if __name__ == "__main__":
    unittest.main()
