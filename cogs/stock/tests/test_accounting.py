"""Accounting invariants: non-negative balances/holdings, supply conserved."""

import asyncio
import unittest

from cogs.stock.config import StockConfig
from cogs.stock.repository import InMemoryRepository
from cogs.stock.service import StockService


class TestAccounting(unittest.TestCase):
    def test_invariants(self):
        async def go():
            cfg = StockConfig()
            repo = InMemoryRepository()
            svc = StockService(repo, cfg)
            await svc.create_stock(1, 100, "bit", "Bit Corp")
            await svc.buy(1, 200, "BIT", 50)
            await svc.buy(1, 201, "BIT", 30)
            await svc.sell(1, 200, "BIT", 20)
            # no negative balances
            for key, bal in repo.balances.items():
                self.assertGreaterEqual(bal, 0, key)
            # no negative holdings
            for key, qty in repo.holdings.items():
                self.assertGreaterEqual(qty, 0, key)
            # supply conserved: available + all holdings == total
            doc = await svc.require_stock(1, "BIT")
            held_total = sum(q for k, q in repo.holdings.items()
                             if k.endswith(f":{doc['_id']}"))
            self.assertEqual(doc["available_shares"] + held_total, doc["total_shares"])
            # every trade has a ledger entry; debits reconcile with fee sink
            self.assertEqual(len(repo.trades), 3)
            for t in repo.trades:
                self.assertEqual(t["gross"], t["quantity"] * t["price"])
                if t["side"] == "buy":
                    self.assertEqual(t["total"], t["gross"] + t["fee"])
                else:
                    self.assertEqual(t["total"], t["gross"] - t["fee"])
        asyncio.run(go())

    def test_ticker_uniqueness_case_insensitive(self):
        async def go():
            cfg = StockConfig()
            repo = InMemoryRepository()
            svc = StockService(repo, cfg)
            await svc.create_stock(1, 100, "bit", "Bit Corp")
            from cogs.stock.exceptions import LimitError
            with self.assertRaises(LimitError):
                await svc.create_stock(1, 101, "BIT", "Clone")
            # stocks are global – same ticker not allowed even in different guild
            with self.assertRaises(LimitError):
                await svc.create_stock(2, 101, "BIT", "Other Guild")
            # also verify global lookup without guild
            doc = await svc.require_stock(None, "BIT")
            self.assertEqual(doc["ticker"], "BIT")
            doc2 = await svc.require_stock(999, "bit")
            self.assertEqual(doc2["ticker"], "BIT")
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
