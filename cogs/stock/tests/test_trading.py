"""Integration-style tests over the in-memory repository (no MongoDB)."""

import unittest

from cogs.stock.config import StockConfig
from cogs.stock.exceptions import (
    InsufficientFundsError,
    InsufficientSharesError,
    LimitError,
    NoSupplyError,
)
from cogs.stock.repository import InMemoryRepository
from cogs.stock.service import StockService


def make_service(**overrides) -> tuple[StockService, InMemoryRepository]:
    cfg = StockConfig(**overrides)
    repo = InMemoryRepository()
    return StockService(repo, cfg), repo


class TestCreation(unittest.TestCase):
    def test_create_and_state(self):
        import asyncio
        # test expects creator allocation 1000 and 9000 available
        svc, repo = make_service(creator_allocation=1000, total_supply=10000, max_trade_quantity=10000, max_position_shares=10000)

        async def go():
            doc = await svc.create_stock(1, 100, "bit", "Bit Corp")
            self.assertEqual(doc["ticker"], "BIT")
            self.assertEqual(doc["available_shares"], 9000)
            holding = await repo.get_holding(1, 100, doc["_id"])
            self.assertEqual(holding, 1000)
            with self.assertRaises(LimitError):
                await svc.create_stock(1, 100, "bit", "Dup")
            with self.assertRaises(LimitError):
                await svc.create_stock(1, 100, "bit2", "Second")
        asyncio.run(go())

    def test_invalid_ticker_rejected(self):
        import asyncio
        svc, _ = make_service()

        async def go():
            with self.assertRaises(Exception):
                await svc.create_stock(1, 101, "x", "Bad")
        asyncio.run(go())


class TestTrading(unittest.TestCase):
    def test_buy_sell_roundtrip(self):
        import asyncio
        svc, repo = make_service(starting_balance_minor=1_000_000, creator_allocation=1000, max_trade_quantity=10000, max_position_shares=10000, min_hold_seconds=0)

        async def go():
            doc = await svc.create_stock(1, 100, "bit", "Bit Corp")
            start_price = doc["current_price"]
            receipt = await svc.buy(1, 200, "BIT", 10)
            self.assertEqual(receipt.quantity, 10)
            self.assertGreaterEqual(receipt.new_price_minor, start_price)  # buy pressure up
            bal = await repo.get_balance(1, 200)
            self.assertLess(bal, 1_000_000)
            # sell back
            receipt2 = await svc.sell(1, 200, "BIT", 10)
            self.assertEqual(await repo.get_holding(1, 200, doc["_id"]), 0)
            self.assertLessEqual(receipt2.new_price_minor, receipt.new_price_minor)
            # supply conserved: available back to 9000
            doc2 = await svc.require_stock(1, "BIT")
            self.assertEqual(doc2["available_shares"], 9000)
        asyncio.run(go())

    def test_insufficient_funds_shares_supply(self):
        import asyncio
        svc, _ = make_service(starting_balance_minor=100, max_trade_quantity=100000, total_supply=100000, max_position_shares=100000, min_hold_seconds=0)

        async def go():
            await svc.create_stock(1, 100, "bit", "Bit Corp")
            with self.assertRaises(InsufficientFundsError):
                await svc.buy(1, 200, "BIT", 10)
            with self.assertRaises(InsufficientSharesError):
                await svc.sell(1, 200, "BIT", 1)
            # deplete then trigger NoSupply within hard cap (use different buyer to avoid position cap)
            svc3, _ = make_service(starting_balance_minor=10_000_000_00, total_supply=2000, max_trade_quantity=2000, max_position_shares=2000, min_hold_seconds=0)
            await svc3.create_stock(1, 100, "LOW", "Low Co")
            await svc3.buy(1, 200, "LOW", 1500)  # leaves 500 available
            with self.assertRaises(NoSupplyError):
                await svc3.buy(1, 201, "LOW", 600)
            # hard cap enforcement
            svc2, _ = make_service(max_trade_quantity=500, max_position_shares=10000, min_hold_seconds=0, total_supply=10000)
            await svc2.create_stock(1, 100, "CAP", "Cap Co")
            from cogs.stock.exceptions import LimitError, ValidationError
            with self.assertRaises((LimitError, ValidationError)):
                await svc2.buy(1, 200, "CAP", 501)
        asyncio.run(go())

    def test_failed_trade_leaves_state_unchanged(self):
        import asyncio
        svc, repo = make_service(min_hold_seconds=0, max_trade_quantity=10000, total_supply=10000, max_position_shares=10000)

        async def go():
            doc = await svc.create_stock(1, 100, "bit", "Bit Corp")
            bal_before = await svc.balance_of(1, 200)
            avail_before = doc["available_shares"]
            with self.assertRaises(Exception):
                await svc.buy(1, 200, "BIT", 0)
            self.assertEqual(await svc.balance_of(1, 200), bal_before)
            doc2 = await svc.require_stock(1, "BIT")
            self.assertEqual(doc2["available_shares"], avail_before)
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
