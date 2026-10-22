"""Use cases: create, buy, sell, portfolio. DB-agnostic over a repository.

Stocks are global (not per-guild). ``guild_id`` parameters are retained for
backwards compatibility but are ignored – all operations are global. Callers
may omit ``guild_id`` or pass ``None``/``0``.
"""

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
        # handle create_stock(owner_id, ticker, name) vs create_stock(guild_id, owner_id, ticker, name)
        if name is None and ticker is not None and isinstance(ticker, str) and owner_id is not None and isinstance(owner_id, int):
            # need to detect overload: if called with 3 args (owner_id, ticker, name)
            # then guild_id is owner_id, owner_id is ticker, ticker is name
            if isinstance(owner_id, str):
                # shouldn't happen
                pass
        # If ticker looks like name and owner_id is ticker string, shift
        # Detect when guild_id is actually owner_id and we have 4 positional args without guild
        # Most reliable: if ticker is not None and name is not None but owner_id is string -> shift
        if isinstance(owner_id, str) and ticker is not None and name is None:
            # create_stock(ticker, name) style – not used
            pass
        # If called as create_stock(owner_id, ticker, name, description) without guild_id:
        # Then guild_id = owner_id, owner_id = ticker (str), ticker = name (str) ...
        # Detect by checking if owner_id is string (ticker)
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
        quantity = validate_quantity(quantity)  # type: ignore
        stock = await self.require_stock(guild_id, ticker)  # type: ignore
        self._require_tradable(stock)
        stock_id = _stock_id(stock)
        price = int(stock["current_price"])
        if int(stock.get("available_shares", 0)) < quantity:
            raise NoSupplyError("Not enough shares available in the offering pool.")
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
        quantity = validate_quantity(quantity)  # type: ignore
        stock = await self.require_stock(guild_id, ticker)  # type: ignore
        self._require_tradable(stock)
        stock_id = _stock_id(stock)
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
