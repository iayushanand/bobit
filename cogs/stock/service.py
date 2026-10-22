"""Use cases: create, buy, sell, portfolio. DB-agnostic over a repository.

Stocks are global (not per-guild). ``guild_id`` parameters are retained for
backwards compatibility but are ignored – all operations are global. Callers
may omit ``guild_id`` or pass ``None``/``0``.
"""

import asyncio
import time

from .config import StockConfig, DEFAULT_CONFIG
from .exceptions import (
    InsufficientFundsError,
    InsufficientSharesError,
    LimitError,
    NoSupplyError,
    NotFoundError,
    TradingHaltedError,
)
from .models import (
    STATUS_ACTIVE,
    TradeReceipt,
    liquidity_for,
    new_stock_doc,
)
from .pricing import apply_return_to_price, quote_trade, trade_impact_return
from .validators import normalize_ticker, validate_description, validate_name, validate_quantity


def _stock_id(doc: dict) -> str:
    return str(doc["_id"])


def _resolve_guild_user(guild_id, user_id):
    """Normalize (guild_id, user_id) where guild is ignored (global)."""
    if user_id is None:
        # called as (user_id,) -> guild_id holds user_id
        user_id = guild_id
        guild_id = 0
    if guild_id is None:
        guild_id = 0
    return guild_id, user_id


class StockService:
    """Business logic; takes any repo with the InMemory/Mongo method names."""

    def __init__(self, repo, config: StockConfig = DEFAULT_CONFIG) -> None:
        self.repo = repo
        self.config = config
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_buy_ts: dict[str, float] = {}  # key = f"{user_id}:{stock_id}"

    def _lock_for(self, stock_id: str) -> asyncio.Lock:
        if stock_id not in self._locks:
            self._locks[stock_id] = asyncio.Lock()
        return self._locks[stock_id]

    def _check_hard_cap(self, quantity: int) -> None:
        if quantity > self.config.max_trade_quantity:
            raise LimitError(f"Hard cap: max {self.config.max_trade_quantity:,} shares per trade (you tried {quantity:,}).")
        validate_quantity(quantity, self.config.max_trade_quantity)

    def _check_position_cap(self, current_holding: int, delta: int) -> None:
        new_qty = current_holding + delta
        if new_qty > self.config.max_position_shares:
            raise LimitError(f"Position cap: max {self.config.max_position_shares:,} shares per stock (you would hold {new_qty:,}).")

    async def _check_global_volume(self, stock_id: str, quantity: int) -> None:
        """Global per-stock volume throttle: sum of all trades in window + this quantity must be <= cap."""
        window_start = time.time() - self.config.global_volume_window_seconds
        try:
            trades = await self.repo.list_trades(None, stock_id, None, 5000)
        except Exception:
            return
        volume = 0
        oldest_in_window = None
        for t in trades:
            ts = float(t.get("ts", 0))
            if ts >= window_start:
                volume += int(t.get("quantity", 0))
                if oldest_in_window is None or ts < oldest_in_window:
                    oldest_in_window = ts
        if volume + quantity > self.config.global_max_volume_per_window:
            # estimate retry: time until oldest trade falls out of window
            if oldest_in_window is not None:
                retry = int((oldest_in_window + self.config.global_volume_window_seconds) - time.time())
                retry = max(1, retry)
            else:
                retry = self.config.global_volume_window_seconds
            raise LimitError(
                f"Global limit: {self.config.global_max_volume_per_window:,} shares per {self.config.global_volume_window_seconds//60}m per stock. "
                f"Already traded {volume:,} in window — try again in {retry}s."
            )

    async def _check_circuit_breaker(self, stock: dict, new_price: int) -> None:
        """Halt if price moved > global_max_price_move_pct within the global window."""
        stock_id = _stock_id(stock)
        window_start = time.time() - self.config.global_volume_window_seconds
        try:
            history = await self.repo.list_price_history(stock_id, 500)
        except Exception:
            return
        window_prices = [h for h in history if float(h.get("ts", 0)) >= window_start]
        if not window_prices:
            return
        # earliest price in window is the window open
        window_prices.sort(key=lambda h: float(h.get("ts", 0)))
        open_price = int(window_prices[0].get("price", stock.get("initial_price", self.config.initial_price_minor)))
        if open_price <= 0:
            return
        move = abs(new_price - open_price) / open_price
        if move > self.config.global_max_price_move_pct:
            raise TradingHaltedError(
                f"Circuit breaker: {stock['ticker']} moved {move*100:.1f}% in {self.config.global_volume_window_seconds//60}m "
                f"(limit {self.config.global_max_price_move_pct*100:.0f}%). Trading halted for {self.config.global_circuit_halt_seconds//60}m."
            )

    def _is_global_halted(self, stock: dict) -> bool:
        # stock may have `global_halt_until` set by breaker — if still in future, consider halted
        halt_until = stock.get("global_halt_until")
        if halt_until is not None:
            if time.time() < float(halt_until):
                return True
            # expired — caller should clear, but treat as not halted here
        return False

    # -- balances -- global per user
    async def balance_of(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> int:
        # handle balance_of(user_id) and balance_of(guild_id, user_id)
        if user_id is None:
            user_id = guild_id
            guild_id = 0
        if user_id is None:
            user_id = kwargs.get("user_id")
        if guild_id is None:
            guild_id = 0
        bal = await self.repo.get_balance(guild_id, user_id)
        if bal is None:
            bal = self.config.starting_balance_minor
            await self.repo.set_balance(guild_id, user_id, bal)
        return int(bal)

    # -- create --
    async def create_stock(self, guild_id: int | None = None, owner_id: int | None = None, ticker: str | None = None,
                           name: str | None = None, description: str | None = None, *args, **kwargs) -> dict:
        if isinstance(owner_id, str):
            description = name  # type: ignore
            name = ticker  # type: ignore
            ticker = owner_id
            owner_id = guild_id  # type: ignore
            guild_id = 0
        if guild_id is None:
            guild_id = 0
        # kwargs fallback
        if ticker is None:
            ticker = kwargs.get("ticker")
        if name is None:
            name = kwargs.get("name")
        if owner_id is None:
            owner_id = kwargs.get("owner_id")
        if description is None:
            description = kwargs.get("description")

        ticker = normalize_ticker(ticker)  # type: ignore
        name = validate_name(name)  # type: ignore
        description = validate_description(description)
        existing = await self.repo.find_stock_by_ticker(guild_id, ticker)
        if existing is not None:
            raise LimitError(f"Ticker `{ticker}` is already taken.")
        owned = await self.repo.count_stocks_by_owner(guild_id, owner_id)
        if owned >= self.config.max_stocks_per_member:
            raise LimitError("You already own the maximum number of stocks.")
        balance = await self.balance_of(guild_id, owner_id)
        if balance < self.config.creation_fee_minor:
            raise InsufficientFundsError("Insufficient funds for the creation fee.")
        if self.config.creation_fee_minor:
            await self.repo.set_balance(guild_id, owner_id, balance - self.config.creation_fee_minor)
        now = time.time()
        doc = new_stock_doc(guild_id, owner_id, ticker, name,
                            self.config.initial_price_minor, self.config.total_supply,
                            self.config.creator_allocation, now, description)
        stock_id = await self.repo.insert_stock(doc)
        doc["_id"] = stock_id
        if self.config.creator_allocation:
            await self.repo.adjust_holding(guild_id, owner_id, stock_id, self.config.creator_allocation)
        await self.repo.insert_price_event({
            "stock_id": stock_id, "guild_id": 0, "ts": now,
            "price": self.config.initial_price_minor, "reason": "genesis",
            "components": {}, "return": 0.0,
        })
        return doc

    async def require_stock(self, guild_id: int | str | None = None, ticker: str | None = None, *args, **kwargs) -> dict:
        # handle require_stock(ticker) and require_stock(guild_id, ticker)
        if ticker is None and isinstance(guild_id, str):
            ticker = guild_id
            guild_id = 0
        if ticker is None:
            ticker = kwargs.get("ticker")
        if guild_id is None:
            guild_id = 0
        ticker = normalize_ticker(ticker)  # type: ignore
        doc = await self.repo.find_stock_by_ticker(guild_id, ticker)
        if doc is None:
            raise NotFoundError(f"Stock `{ticker}` not found.")
        return doc

    def _require_tradable(self, stock: dict) -> None:
        if stock.get("status") != STATUS_ACTIVE:
            raise TradingHaltedError(f"`{stock['ticker']}` is not tradable ({stock.get('status')}).")
        # global circuit breaker halt
        halt_until = stock.get("global_halt_until")
        if halt_until is not None:
            try:
                if time.time() < float(halt_until):
                    remain = int(float(halt_until) - time.time())
                    raise TradingHaltedError(f"`{stock['ticker']}` is halted by circuit breaker — try again in {remain}s.")
            except (ValueError, TypeError):
                pass

    # -- buy / sell --
    async def buy(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, quantity: int | None = None, *args, **kwargs) -> TradeReceipt:
        # handle buy(user_id, ticker, quantity) vs buy(guild_id, user_id, ticker, quantity)
        if quantity is None:
            # shift: guild_id=user_id, user_id=ticker, ticker=quantity
            if isinstance(user_id, str):
                quantity = ticker  # type: ignore
                ticker = user_id  # type: ignore
                user_id = guild_id  # type: ignore
                guild_id = 0
            else:
                quantity = kwargs.get("quantity")
                if ticker is None:
                    ticker = kwargs.get("ticker")
                if user_id is None:
                    user_id = kwargs.get("user_id")
        if guild_id is None:
            guild_id = 0
        quantity = validate_quantity(quantity, self.config.max_trade_quantity)  # type: ignore
        self._check_hard_cap(quantity)
        stock = await self.require_stock(guild_id, ticker)  # type: ignore
        self._require_tradable(stock)
        stock_id = _stock_id(stock)
        pre_holding = await self.repo.get_holding(guild_id, user_id, stock_id)
        self._check_position_cap(pre_holding, quantity)
        async with self._lock_for(stock_id):
            stock = await self.require_stock(guild_id, ticker)  # type: ignore
            self._require_tradable(stock)
            # global volume throttle
            await self._check_global_volume(stock_id, quantity)
            price = int(stock["current_price"])
            if int(stock.get("available_shares", 0)) < quantity:
                raise NoSupplyError("Not enough shares available in the offering pool.")
            holding_now = await self.repo.get_holding(guild_id, user_id, stock_id)
            self._check_position_cap(holding_now, quantity)
            quote = quote_trade(quantity, price, self.config.trading_fee_rate, True)
            balance = await self.balance_of(guild_id, user_id)
            if balance < quote.total_minor:
                raise InsufficientFundsError("Insufficient funds for this purchase.")
            liquidity = liquidity_for(price, int(stock.get("available_shares", 0)),
                                       self.config.minimum_liquidity_minor)
            impact = trade_impact_return(quote.gross_minor, liquidity, self.config.trade_sensitivity,
                                         self.config.minimum_liquidity_minor, self.config.max_trade_move)
            new_price = apply_return_to_price(price, impact, self.config.min_price_minor,
                                              self.config.max_price_minor)
            # circuit breaker on resulting price
            try:
                await self._check_circuit_breaker(stock, new_price)
            except TradingHaltedError:
                # persist halt so all traders see it
                halt_until = time.time() + self.config.global_circuit_halt_seconds
                try:
                    await self.repo.update_stock(stock_id, {"global_halt_until": halt_until})
                except Exception:
                    pass
                raise
            now = time.time()
            await self.repo.set_balance(guild_id, user_id, balance - quote.total_minor)
            await self.repo.adjust_holding(guild_id, user_id, stock_id, quantity)
            await self.repo.update_stock(stock_id, {
                "current_price": new_price,
                "available_shares": int(stock.get("available_shares", 0)) - quantity,
                "liquidity": liquidity_for(new_price, int(stock.get("available_shares", 0)) - quantity,
                                           self.config.minimum_liquidity_minor),
                "last_price_update_at": now,
            })
            await self.repo.insert_trade({
                "stock_id": stock_id, "guild_id": 0, "user_id": user_id,
                "side": "buy", "quantity": quantity, "price": price,
                "gross": quote.gross_minor, "fee": quote.fee_minor,
                "total": quote.total_minor, "ts": now,
            })
            await self.repo.insert_price_event({
                "stock_id": stock_id, "guild_id": 0, "ts": now,
                "price": new_price, "reason": "trade_buy",
                "components": {"trade": impact}, "return": impact,
            })
            self._last_buy_ts[f"{user_id}:{stock_id}"] = now
            return TradeReceipt(ticker, quantity, price, quote.gross_minor,  # type: ignore
                                quote.fee_minor, quote.total_minor, new_price, True)

    async def sell(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, quantity: int | None = None, *args, **kwargs) -> TradeReceipt:
        if quantity is None:
            if isinstance(user_id, str):
                quantity = ticker  # type: ignore
                ticker = user_id  # type: ignore
                user_id = guild_id  # type: ignore
                guild_id = 0
            else:
                quantity = kwargs.get("quantity")
                if ticker is None:
                    ticker = kwargs.get("ticker")
                if user_id is None:
                    user_id = kwargs.get("user_id")
        if guild_id is None:
            guild_id = 0
        quantity = validate_quantity(quantity, self.config.max_trade_quantity)  # type: ignore
        self._check_hard_cap(quantity)
        stock = await self.require_stock(guild_id, ticker)  # type: ignore
        self._require_tradable(stock)
        stock_id = _stock_id(stock)
        # min-hold enforcement: prevent instant flip
        last_buy = self._last_buy_ts.get(f"{user_id}:{stock_id}")
        if last_buy is not None and self.config.min_hold_seconds > 0:
            elapsed = time.time() - last_buy
            if elapsed < self.config.min_hold_seconds:
                raise LimitError(f"Hold period: wait {self.config.min_hold_seconds - int(elapsed)}s before selling `{stock['ticker']}` (anti-flip).")
        async with self._lock_for(stock_id):
            stock = await self.require_stock(guild_id, ticker)  # type: ignore
            self._require_tradable(stock)
            await self._check_global_volume(stock_id, quantity)
            price = int(stock["current_price"])
            holding = await self.repo.get_holding(guild_id, user_id, stock_id)
            if holding < quantity:
                raise InsufficientSharesError("You do not own that many shares.")
            quote = quote_trade(quantity, price, self.config.trading_fee_rate, False)
            liquidity = liquidity_for(price, int(stock.get("available_shares", 0)),
                                       self.config.minimum_liquidity_minor)
            impact = trade_impact_return(-quote.gross_minor, liquidity, self.config.trade_sensitivity,
                                         self.config.minimum_liquidity_minor, self.config.max_trade_move)
            new_price = apply_return_to_price(price, impact, self.config.min_price_minor,
                                              self.config.max_price_minor)
            try:
                await self._check_circuit_breaker(stock, new_price)
            except TradingHaltedError:
                halt_until = time.time() + self.config.global_circuit_halt_seconds
                try:
                    await self.repo.update_stock(stock_id, {"global_halt_until": halt_until})
                except Exception:
                    pass
                raise
            now = time.time()
            balance = await self.balance_of(guild_id, user_id)
            await self.repo.set_balance(guild_id, user_id, balance + quote.total_minor)
            await self.repo.adjust_holding(guild_id, user_id, stock_id, -quantity)
            await self.repo.update_stock(stock_id, {
                "current_price": new_price,
                "available_shares": int(stock.get("available_shares", 0)) + quantity,
                "liquidity": liquidity_for(new_price, int(stock.get("available_shares", 0)) + quantity,
                                           self.config.minimum_liquidity_minor),
                "last_price_update_at": now,
            })
            await self.repo.insert_trade({
                "stock_id": stock_id, "guild_id": 0, "user_id": user_id,
                "side": "sell", "quantity": quantity, "price": price,
                "gross": quote.gross_minor, "fee": quote.fee_minor,
                "total": quote.total_minor, "ts": now,
            })
            await self.repo.insert_price_event({
                "stock_id": stock_id, "guild_id": 0, "ts": now,
                "price": new_price, "reason": "trade_sell",
                "components": {"trade": impact}, "return": impact,
            })
            return TradeReceipt(ticker, quantity, price, quote.gross_minor,  # type: ignore
                                quote.fee_minor, quote.total_minor, new_price, False)

    # -- reads --
    async def portfolio(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> dict:
        if user_id is None:
            user_id = guild_id
            guild_id = 0
        if user_id is None:
            user_id = kwargs.get("user_id")
        if guild_id is None:
            guild_id = 0
        balance = await self.balance_of(guild_id, user_id)
        holdings = await self.repo.list_holdings(guild_id, user_id)
        positions = []
        total_value = 0
        for h in holdings:
            stock = await self.repo.find_stock_by_id(h["stock_id"])
            if stock is None:
                continue
            value = int(stock["current_price"]) * int(h["quantity"])
            total_value += value
            positions.append({"ticker": stock["ticker"], "name": stock.get("name", ""),
                              "quantity": h["quantity"], "price": int(stock["current_price"]),
                              "value": value})
        positions.sort(key=lambda p: p["value"], reverse=True)
        return {"balance": balance, "positions": positions,
                "holdings_value": total_value, "net_worth": balance + total_value}

    async def market_overview(self, guild_id: int | None = None) -> list[dict]:
        stocks = await self.repo.list_all_stocks(guild_id if guild_id is not None else 0)
        return sorted(stocks, key=lambda s: int(s.get("current_price", 0)), reverse=True)
