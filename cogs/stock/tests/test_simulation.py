"""Deterministic multi-day simulation tests (README Section 9).

Scenarios: quiet stock, active owner+holders with trades, spam +
wash-trading, downtime restart. All use fixed seeds; no randomness
leaks into assertions beyond bounded ranges.
"""

import random
import time
import unittest

from cogs.stock.config import StockConfig
from cogs.stock.market_tasks import update_one_stock
from cogs.stock.repository import InMemoryRepository
from cogs.stock.service import StockService


async def _run_quiet(cfg, days=3):
    repo = InMemoryRepository()
    svc = StockService(repo, cfg)
    await svc.create_stock(1, 100, "QUIET", "Quiet Co")
    rnd = random.Random(7)
    now = time.time()
    start = (await svc.require_stock(1, "QUIET"))["current_price"]
    for i in range(days * 24 * 6):
        doc = await svc.require_stock(1, "QUIET")
        await update_one_stock(repo, doc, cfg, now + i * 600, rnd)
    end = (await svc.require_stock(1, "QUIET"))["current_price"]
    return start, end


async def _run_busy(cfg, days=2):
    repo = InMemoryRepository()
    svc = StockService(repo, cfg)
    await svc.create_stock(1, 100, "BUSY", "Busy Co")
    await svc.buy(1, 201, "BUSY", 50)
    rnd = random.Random(3)
    now = time.time()
    doc = await svc.require_stock(1, "BUSY")
    sid, start = doc["_id"], doc["current_price"]
    for i in range(days * 24 * 6):
        t = now + i * 600
        for uid, role in ((100, "owner"), (201, "holder")):
            await repo.record_activity({"stock_id": sid, "guild_id": 1,
                                        "user_id": uid, "role": role, "ts": t})
        doc = await svc.require_stock(1, "BUSY")
        await update_one_stock(repo, doc, cfg, t, rnd)
    end = (await svc.require_stock(1, "BUSY"))["current_price"]
    return start, end


class TestSimulation(unittest.TestCase):
    def test_quiet_decays_gradually_no_collapse(self):
        import asyncio
        cfg = StockConfig()
        start, end = asyncio.run(_run_quiet(cfg))
        change = (end - start) / start
        self.assertLess(change, 0.0, "quiet stock should drift down")
        self.assertGreater(change, -0.20, "3-day quiet decay must stay bounded")
        self.assertGreater(end, 0)

    def test_active_outperforms_quiet(self):
        import asyncio
        cfg = StockConfig()
        qs, qe = asyncio.run(_run_quiet(cfg))
        bs, be = asyncio.run(_run_busy(cfg))
        self.assertGreater((be - bs) / bs, (qe - qs) / qs)

    def test_spam_capped_and_wash_neutral(self):
        import asyncio
        cfg = StockConfig()

        async def go():
            repo = InMemoryRepository()
            svc = StockService(repo, cfg)
            await svc.create_stock(1, 100, "SPAM", "Spam Co")
            rnd = random.Random(9)
            now = time.time()
            doc = await svc.require_stock(1, "SPAM")
            sid, start = doc["_id"], doc["current_price"]
            for i in range(24 * 6):
                t = now + i * 600
                for _ in range(50):
                    await repo.record_activity({"stock_id": sid, "guild_id": 1,
                                                "user_id": 201, "role": "holder", "ts": t})
                doc = await svc.require_stock(1, "SPAM")
                await update_one_stock(repo, doc, cfg, t, rnd)
            end = (await svc.require_stock(1, "SPAM"))["current_price"]
            # spam for a day must not pump more than ~2%
            self.assertLess((end - start) / start, 0.02 + 0.01)
            await svc.buy(1, 202, "SPAM", 5)
            mid = (await svc.require_stock(1, "SPAM"))["current_price"]
            await svc.sell(1, 202, "SPAM", 5)
            final = (await svc.require_stock(1, "SPAM"))["current_price"]
            self.assertGreater(mid, end)  # buy pushes up
            self.assertLess(final, mid)  # sell pushes down
            self.assertGreater(final, 0)
        asyncio.run(go())

    def test_downtime_restart_single_bounded_move(self):
        import asyncio
        cfg = StockConfig()

        async def go():
            repo = InMemoryRepository()
            svc = StockService(repo, cfg)
            await svc.create_stock(1, 100, "DOWN", "Down Co")
            doc = await svc.require_stock(1, "DOWN")
            old = doc["current_price"]
            event = await update_one_stock(repo, doc, cfg, time.time() + 7 * 86400,
                                           random.Random(0))
            self.assertGreaterEqual(event["price"], int(old * (1 - cfg.max_scheduled_move)) - 5)
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
