"""Persistence for the stock market: MongoDB + in-memory (tests).

Stocks are now global (not guild-scoped). ``guild_id`` parameters are
retained for backwards compatibility but are ignored – all queries are
global. New documents store ``guild_id = 0`` as sentinel.
"""

import time
from typing import Any

_ACTIVITY_TTL = 7200  # 2h
_PRICE_TTL = 259200  # 3d
_TRADE_TTL = 604800  # 7d
_MAX_ACTIVITY_DOCS = 20000
_MAX_PRICE_PER_STOCK = 500
_MAX_TRADE_DOCS = 20000


def _holding_key(guild_id: int | str, user_id: int | str | None = None, stock_id: str | None = None) -> str:
    """Backwards-compatible key builder.

    New format: ``{user_id}:{stock_id}`` (global).
    Legacy format: ``{guild_id}:{user_id}:{stock_id}`` – still readable.
    """
    if stock_id is None:
        # called as _holding_key(user_id, stock_id)
        return f"{guild_id}:{user_id}"
    # called as _holding_key(guild_id, user_id, stock_id) – ignore guild
    return f"{user_id}:{stock_id}"


def _balance_key(user_id: int) -> str:
    return str(int(user_id))


def _watch_key(user_id: int) -> str:
    return str(int(user_id))


class InMemoryRepository:
    """Duck-typed store used by unit tests (no MongoDB needed)."""

    def __init__(self) -> None:
        self.stocks: dict[str, dict] = {}
        self.balances: dict[str, int] = {}
        self.holdings: dict[str, int] = {}
        self.trades: list[dict] = []
        self.prices: list[dict] = []
        self.activity: list[dict] = []
        self.watchlists: dict[str, set[str]] = {}
        self.alerts: list[dict] = []
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq}_{int(time.time() * 1000)}"

    def _prune_activity(self, now: float | None = None) -> None:
        if not self.activity:
            return
        now = time.time() if now is None else now
        cutoff = now - _ACTIVITY_TTL
        self.activity = [a for a in self.activity if float(a.get("ts", 0)) >= cutoff]
        if len(self.activity) > _MAX_ACTIVITY_DOCS:
            self.activity = self.activity[-_MAX_ACTIVITY_DOCS:]

    def _prune_prices(self, now: float | None = None) -> None:
        if not self.prices:
            return
        now = time.time() if now is None else now
        cutoff = now - _PRICE_TTL
        self.prices = [p for p in self.prices if float(p.get("ts", 0)) >= cutoff]
        if len(self.prices) > _MAX_PRICE_PER_STOCK * max(1, len(self.stocks)):
            from collections import defaultdict
            by_stock: dict[str, list[dict]] = defaultdict(list)
            for p in self.prices:
                by_stock[str(p.get("stock_id"))].append(p)
            pruned: list[dict] = []
            for lst in by_stock.values():
                lst.sort(key=lambda x: float(x.get("ts", 0)))
                pruned.extend(lst[-_MAX_PRICE_PER_STOCK:])
            pruned.sort(key=lambda x: float(x.get("ts", 0)))
            self.prices = pruned

    def _prune_trades(self, now: float | None = None) -> None:
        if not self.trades:
            return
        now = time.time() if now is None else now
        cutoff = now - _TRADE_TTL
        self.trades = [t for t in self.trades if float(t.get("ts", 0)) >= cutoff]
        if len(self.trades) > _MAX_TRADE_DOCS:
            self.trades = self.trades[-_MAX_TRADE_DOCS:]

    async def ensure_indexes(self) -> None:
        return None

    async def prune_expired(self, now: float | None = None) -> dict:
        before = (len(self.activity), len(self.prices), len(self.trades))
        self._prune_activity(now)
        self._prune_prices(now)
        self._prune_trades(now)
        after = (len(self.activity), len(self.prices), len(self.trades))
        return {"activity": (before[0], after[0]), "prices": (before[1], after[1]), "trades": (before[2], after[2])}

    # -- stocks -- global lookup
    async def find_stock_by_ticker(self, guild_id: int | str | None = None, ticker: str | None = None, *args, **kwargs) -> dict | None:
        # Handle both signatures: (guild_id, ticker) and (ticker,) and (ticker=ticker)
        if ticker is None:
            if isinstance(guild_id, str):
                ticker = guild_id
            else:
                # ticker passed as kwarg?
                ticker = kwargs.get("ticker")
        if ticker is None:
            return None
        for doc in self.stocks.values():
            if doc["ticker"] == ticker:
                return dict(doc)
        return None

    async def find_stock_by_id(self, stock_id: str) -> dict | None:
        doc = self.stocks.get(stock_id)
        return dict(doc) if doc else None

    async def count_stocks_by_owner(self, guild_id: int | None = None, owner_id: int | None = None, *args, **kwargs) -> int:
        # allow (owner_id,) signature
        if owner_id is None and guild_id is not None and isinstance(guild_id, int):
            # check if second arg missing – might be called as count_stocks_by_owner(owner_id)
            # but old signature is (guild_id, owner_id); detect via kwargs
            owner_id = kwargs.get("owner_id")
            if owner_id is None:
                # guild_id actually is owner_id when called with single arg
                # we can't distinguish; assume guild_id is owner_id if count is called with one int
                # however old code always passes 2 args, so this branch is for new global calls
                owner_id = guild_id
        if owner_id is None:
            owner_id = kwargs.get("owner_id")
        if owner_id is None:
            return 0
        return sum(1 for d in self.stocks.values() if d["owner_user_id"] == int(owner_id))

    async def list_active_stocks(self, guild_id: int | None = None) -> list[dict]:
        return [dict(d) for d in self.stocks.values() if d["status"] == "active"]

    async def list_all_stocks(self, guild_id: int | None = None) -> list[dict]:
        return [dict(d) for d in self.stocks.values()]

    async def insert_stock(self, doc: dict) -> str:
        stock_id = self._next_id("stock")
        doc = dict(doc)
        doc["_id"] = stock_id
        # ensure global sentinel
        doc["guild_id"] = 0
        self.stocks[stock_id] = doc
        return stock_id

    async def update_stock(self, stock_id: str, update: dict) -> None:
        self.stocks[stock_id].update(update)

    # -- balances -- global per user
    async def get_balance(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> int | None:
        if user_id is None:
            # called as get_balance(user_id)
            user_id = guild_id  # type: ignore
            guild_id = None
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None:
            return None
        # try new key first, then legacy guild-scoped keys
        key = _balance_key(int(user_id))
        if key in self.balances:
            return self.balances[key]
        # fallback: any legacy key ending with :user_id
        suffix = f":{user_id}"
        for k, v in self.balances.items():
            if k == key or k.endswith(suffix):
                return v
        return None

    async def set_balance(self, guild_id: int | None = None, user_id: int | None = None, balance: int | None = None, *args, **kwargs) -> None:
        # handle (user_id, balance) and (guild_id, user_id, balance)
        if balance is None:
            if user_id is not None and guild_id is not None:
                # called as set_balance(guild_id, user_id, balance) where guild_id is actually user_id?
                # Normal 3-arg call: guild_id, user_id, balance
                balance = kwargs.get("balance", args[0] if args else None)  # type: ignore
                # if balance still None, shift
                if balance is None and isinstance(user_id, int):
                    # assume set_balance(user_id, balance)
                    balance = user_id  # type: ignore
                    user_id = guild_id  # type: ignore
            elif user_id is not None:
                # called as set_balance(user_id, balance) where guild_id is user_id, user_id is balance
                balance = user_id  # type: ignore
                user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if balance is None:
            balance = kwargs.get("balance")
        if user_id is None or balance is None:
            return
        # migrate legacy keys: remove old entries for this user
        suffix = f":{user_id}"
        for k in list(self.balances.keys()):
            if k.endswith(suffix) and k != _balance_key(int(user_id)):
                self.balances.pop(k, None)
        self.balances[_balance_key(int(user_id))] = int(balance)

    # -- holdings -- global per user
    async def get_holding(self, guild_id: int | None = None, user_id: int | None = None, stock_id: str | None = None, *args, **kwargs) -> int:
        # handle (user_id, stock_id) and (guild_id, user_id, stock_id)
        if stock_id is None:
            if user_id is not None and guild_id is not None:
                # 2-arg: guild_id=user_id, user_id=stock_id
                stock_id = str(user_id)
                user_id = guild_id  # type: ignore
            else:
                stock_id = kwargs.get("stock_id")
                if user_id is None:
                    user_id = kwargs.get("user_id")
        if user_id is None or stock_id is None:
            return 0
        key = _holding_key(int(user_id), stock_id)
        if key in self.holdings:
            return self.holdings[key]
        # legacy 3-part key fallback
        legacy_suffix = f":{user_id}:{stock_id}"
        for k, v in self.holdings.items():
            if k.endswith(legacy_suffix):
                return v
        # also try direct legacy with guild
        return 0

    async def list_holdings(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> list[dict]:
        if user_id is None:
            user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None:
            return []
        uid = int(user_id)
        out = []
        for key, qty in self.holdings.items():
            if qty <= 0:
                continue
            parts = key.split(":")
            if len(parts) == 2:
                u, s = parts
                if int(u) == uid:
                    out.append({"stock_id": s, "quantity": qty})
            elif len(parts) == 3:
                g, u, s = parts
                if int(u) == uid:
                    out.append({"stock_id": s, "quantity": qty})
        return out

    async def list_holders(self, stock_id: str) -> list[dict]:
        out = []
        for key, qty in self.holdings.items():
            if qty <= 0:
                continue
            parts = key.split(":")
            s = parts[-1]
            u = parts[-2] if len(parts) >= 2 else None
            if s == stock_id and u is not None:
                out.append({"user_id": int(u), "quantity": qty})
        return out

    async def adjust_holding(self, guild_id: int | None = None, user_id: int | None = None, stock_id: str | None = None, delta: int | None = None, *args, **kwargs) -> int:
        # handle (user_id, stock_id, delta) and (guild_id, user_id, stock_id, delta)
        if delta is None:
            # need to shift
            if stock_id is not None and user_id is not None and guild_id is not None:
                # Check if called with 3 args: (user_id, stock_id, delta)
                # Then guild_id=user_id, user_id=stock_id, stock_id=delta
                try:
                    # if stock_id is actually int delta?
                    delta = int(stock_id)  # type: ignore
                    stock_id = str(user_id)
                    user_id = guild_id  # type: ignore
                except Exception:
                    delta = kwargs.get("delta")
            else:
                delta = kwargs.get("delta")
        if stock_id is None:
            stock_id = kwargs.get("stock_id")
        if user_id is None:
            user_id = kwargs.get("user_id")
        if delta is None:
            delta = 0
        if user_id is None or stock_id is None:
            raise ValueError("user_id and stock_id required")
        # migrate legacy key if exists
        legacy_key = None
        for k in list(self.holdings.keys()):
            parts = k.split(":")
            if len(parts) == 3 and parts[1] == str(user_id) and parts[2] == stock_id:
                legacy_key = k
                break
        key = _holding_key(int(user_id), stock_id)
        # if legacy exists and new not, migrate
        if legacy_key and key not in self.holdings:
            self.holdings[key] = self.holdings.pop(legacy_key)
        new_qty = self.holdings.get(key, 0) + int(delta)
        if new_qty < 0:
            raise ValueError("holdings cannot go negative")
        if new_qty == 0:
            self.holdings.pop(key, None)
            if legacy_key:
                self.holdings.pop(legacy_key, None)
        else:
            self.holdings[key] = new_qty
            if legacy_key:
                self.holdings.pop(legacy_key, None)
        return new_qty

    # -- trades / prices / activity --
    async def insert_trade(self, doc: dict) -> str:
        doc = dict(doc)
        doc["_id"] = self._next_id("trade")
        doc["guild_id"] = 0
        self.trades.append(doc)
        if len(self.trades) % 100 == 0:
            self._prune_trades(float(doc.get("ts", time.time())))
        elif len(self.trades) > _MAX_TRADE_DOCS:
            self._prune_trades(float(doc.get("ts", time.time())))
        return doc["_id"]

    async def list_trades(self, guild_id: int | None = None, stock_id: str | None = None,
                          user_id: int | None = None, limit: int = 20, *args, **kwargs) -> list[dict]:
        # handle guild_id being actually stock_id when called with fewer args
        # Normalize: if guild_id is string and stock_id is int, shift not needed
        # For backwards compat, guild_id filter is ignored (global)
        # But support calling as list_trades(stock_id, user_id) or list_trades(guild_id, stock_id, user_id)
        # Detect if guild_id looks like stock_id (contains underscore)
        if isinstance(guild_id, str) and stock_id is None and user_id is None:
            # ambiguous; treat guild_id as stock_id
            pass
        # if guild_id is int and stock_id is None -> guild filter ignored
        # Actually just filter by stock_id and user_id globally
        out = [t for t in self.trades
               if (stock_id is None or t["stock_id"] == stock_id)
               and (user_id is None or t["user_id"] == user_id)]
        # also handle case where guild_id is actually stock_id string with underscore
        # No guild filtering
        return list(reversed(out[-limit:]))

    async def insert_price_event(self, doc: dict) -> str:
        doc = dict(doc)
        doc["_id"] = self._next_id("price")
        doc["guild_id"] = 0
        self.prices.append(doc)
        if len(self.prices) % 100 == 0:
            self._prune_prices(float(doc.get("ts", time.time())))
        return doc["_id"]

    async def list_price_history(self, stock_id: str, limit: int = 100) -> list[dict]:
        out = [p for p in self.prices if p["stock_id"] == stock_id]
        return out[-limit:]

    async def record_activity(self, doc: dict) -> None:
        doc = dict(doc)
        doc["guild_id"] = 0
        self.activity.append(doc)
        if len(self.activity) % 200 == 0:
            self._prune_activity(float(doc.get("ts", time.time())))
        elif len(self.activity) > _MAX_ACTIVITY_DOCS:
            self._prune_activity(float(doc.get("ts", time.time())))

    async def activity_since(self, stock_id: str, since_ts: float) -> list[dict]:
        return [a for a in self.activity if a["stock_id"] == stock_id and a["ts"] >= since_ts]

    async def last_owner_activity(self, stock_id: str, owner_id: int) -> float | None:
        ts = [a["ts"] for a in self.activity
              if a["stock_id"] == stock_id and a["user_id"] == owner_id]
        return max(ts) if ts else None

    # -- watchlists / alerts -- global per user
    async def watch_add(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, *args, **kwargs) -> None:
        if ticker is None:
            # called as watch_add(user_id, ticker)
            ticker = user_id  # type: ignore
            user_id = guild_id  # type: ignore
        if ticker is None:
            ticker = kwargs.get("ticker")
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None or ticker is None:
            return
        key = _watch_key(int(user_id))
        self.watchlists.setdefault(key, set()).add(ticker)
        # migrate legacy
        for k in list(self.watchlists.keys()):
            if k.endswith(f":{user_id}") and k != key:
                self.watchlists[key].update(self.watchlists.pop(k))

    async def watch_remove(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, *args, **kwargs) -> None:
        if ticker is None:
            ticker = user_id  # type: ignore
            user_id = guild_id  # type: ignore
        if ticker is None:
            ticker = kwargs.get("ticker")
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None or ticker is None:
            return
        key = _watch_key(int(user_id))
        self.watchlists.get(key, set()).discard(ticker)

    async def watch_list(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> list[str]:
        if user_id is None:
            user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None:
            return []
        key = _watch_key(int(user_id))
        # include legacy
        result = set(self.watchlists.get(key, set()))
        suffix = f":{user_id}"
        for k, v in self.watchlists.items():
            if k.endswith(suffix) and k != key:
                result.update(v)
        return sorted(result)

    async def alert_add(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, price: float | None = None, *args, **kwargs) -> str:
        if price is None:
            # handle (user_id, ticker, price) vs (guild_id, user_id, ticker, price)
            if ticker is not None and isinstance(ticker, (int, float)):
                price = float(ticker)
                ticker = user_id  # type: ignore
                user_id = guild_id  # type: ignore
            else:
                price = kwargs.get("price")
                if ticker is None:
                    ticker = kwargs.get("ticker")
                if user_id is None:
                    user_id = kwargs.get("user_id")
        alert_id = self._next_id("alert")
        self.alerts.append({"_id": alert_id, "guild_id": 0, "user_id": int(user_id) if user_id is not None else 0,
                            "ticker": ticker, "price_minor": int(round(float(price) * 100)) if price is not None else 0,
                            "triggered": False})
        return alert_id

    async def alerts_for_stock(self, guild_id: int | None = None, ticker: str | None = None, *args, **kwargs) -> list[dict]:
        if ticker is None:
            ticker = guild_id  # type: ignore
        if ticker is None:
            ticker = kwargs.get("ticker")
        if ticker is None:
            return []
        return [a for a in self.alerts if a["ticker"] == ticker and not a["triggered"]]

    async def mark_alert_triggered(self, alert_id: str) -> None:
        for a in self.alerts:
            if a["_id"] == alert_id:
                a["triggered"] = True


class MongoRepository:
    """MongoDB-backed store with the same method names as InMemoryRepository."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def ensure_indexes(self) -> None:
        try:
            await self._db.stock_stocks.create_index([("ticker", 1)], unique=True)
            await self._db.stock_holdings.create_index(
                [("user_id", 1), ("stock_id", 1)], unique=True)
            await self._db.stock_balances.create_index(
                [("user_id", 1)], unique=True)
            await self._db.stock_prices.create_index([("stock_id", 1), ("ts", 1)])
            await self._db.stock_trades.create_index([("ts", -1)])
            await self._db.stock_activity.create_index([("stock_id", 1), ("ts", 1)])
            try:
                await self._db.stock_activity.create_index([("ts", 1)], expireAfterSeconds=_ACTIVITY_TTL)
            except Exception:
                pass
            try:
                await self._db.stock_prices.create_index([("ts", 1)], expireAfterSeconds=_PRICE_TTL)
            except Exception:
                pass
            try:
                await self._db.stock_trades.create_index([("ts", 1)], expireAfterSeconds=_TRADE_TTL)
            except Exception:
                pass
        except Exception:
            pass

    async def prune_expired(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        result: dict = {}
        try:
            cutoff_a = now - _ACTIVITY_TTL
            res = await self._db.stock_activity.delete_many({"ts": {"$lt": cutoff_a}})
            result["activity"] = getattr(res, "deleted_count", 0)
        except Exception:
            result["activity"] = 0
        try:
            cutoff_p = now - _PRICE_TTL
            res = await self._db.stock_prices.delete_many({"ts": {"$lt": cutoff_p}})
            result["prices"] = getattr(res, "deleted_count", 0)
        except Exception:
            result["prices"] = 0
        try:
            cutoff_t = now - _TRADE_TTL
            res = await self._db.stock_trades.delete_many({"ts": {"$lt": cutoff_t}})
            result["trades"] = getattr(res, "deleted_count", 0)
        except Exception:
            result["trades"] = 0
        return result

    # -- stocks --
    async def find_stock_by_ticker(self, guild_id: int | str | None = None, ticker: str | None = None, *args, **kwargs) -> dict | None:
        if ticker is None and isinstance(guild_id, str):
            ticker = guild_id
        if ticker is None:
            ticker = kwargs.get("ticker")
        if ticker is None:
            return None
        return await self._db.stock_stocks.find_one({"ticker": ticker})

    async def find_stock_by_id(self, stock_id: str) -> dict | None:
        from bson import ObjectId
        try:
            oid = ObjectId(stock_id)
        except Exception:
            return await self._db.stock_stocks.find_one({"_id": stock_id})
        return await self._db.stock_stocks.find_one({"_id": oid})

    async def count_stocks_by_owner(self, guild_id: int | None = None, owner_id: int | None = None, *args, **kwargs) -> int:
        if owner_id is None:
            if isinstance(guild_id, int):
                owner_id = guild_id
            else:
                owner_id = kwargs.get("owner_id")
        if owner_id is None:
            return 0
        return await self._db.stock_stocks.count_documents(
            {"owner_user_id": int(owner_id)})

    async def list_active_stocks(self, guild_id: int | None = None) -> list[dict]:
        cursor = self._db.stock_stocks.find({"status": "active"})
        return await cursor.to_list(length=200)

    async def list_all_stocks(self, guild_id: int | None = None) -> list[dict]:
        cursor = self._db.stock_stocks.find({})
        return await cursor.to_list(length=200)

    async def insert_stock(self, doc: dict) -> str:
        doc = dict(doc)
        doc["guild_id"] = 0
        res = await self._db.stock_stocks.insert_one(doc)
        return str(res.inserted_id)

    async def update_stock(self, stock_id: str, update: dict) -> None:
        from bson import ObjectId
        try:
            oid: Any = ObjectId(stock_id)
        except Exception:
            oid = stock_id
        await self._db.stock_stocks.update_one({"_id": oid}, {"$set": update})

    # -- balances --
    async def get_balance(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> int | None:
        if user_id is None and guild_id is not None:
            user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None:
            return None
        doc = await self._db.stock_balances.find_one({"user_id": int(user_id)})
        if doc:
            return int(doc["balance"])
        # legacy fallback
        doc = await self._db.stock_balances.find_one({"user_id": int(user_id)})
        return int(doc["balance"]) if doc else None

    async def set_balance(self, guild_id: int | None = None, user_id: int | None = None, balance: int | None = None, *args, **kwargs) -> None:
        if balance is None and user_id is not None and guild_id is not None:
            # distinguish (guild_id, user_id, balance) vs (user_id, balance)
            # if user_id is int and balance is int, and guild_id is int
            # need to see if called with 2 args: guild_id=user_id, user_id=balance
            # Check arg count via kwargs not reliable; handle heuristic
            if isinstance(guild_id, int) and isinstance(user_id, int) and isinstance(balance, int):
                pass  # 3-arg normal
            elif isinstance(user_id, int) and balance is None:
                balance = user_id  # type: ignore
                user_id = guild_id  # type: ignore
        if balance is None:
            # handle (user_id, balance) where guild_id is user_id
            if user_id is None and guild_id is not None:
                # shouldn't happen
                pass
            if isinstance(guild_id, int) and isinstance(user_id, int) and balance is None:
                # actually called as set_balance(user_id, balance) -> guild_id=user_id, user_id=balance
                if args:
                    balance = args[0]  # type: ignore
                else:
                    balance = user_id  # type: ignore
                    user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if balance is None:
            balance = kwargs.get("balance")
            if balance is None and args:
                balance = args[0]  # type: ignore
        if user_id is None or balance is None:
            return
        await self._db.stock_balances.update_one(
            {"user_id": int(user_id)},
            {"$set": {"balance": int(balance)}}, upsert=True)

    # -- holdings --
    async def get_holding(self, guild_id: int | None = None, user_id: int | None = None, stock_id: str | None = None, *args, **kwargs) -> int:
        if stock_id is None:
            if isinstance(user_id, str):
                stock_id = user_id
                user_id = guild_id  # type: ignore
            else:
                stock_id = kwargs.get("stock_id")
                if user_id is None:
                    user_id = kwargs.get("user_id")
                    if user_id is None and guild_id is not None:
                        user_id = guild_id  # type: ignore
        if user_id is None or stock_id is None:
            return 0
        doc = await self._db.stock_holdings.find_one(
            {"user_id": int(user_id), "stock_id": stock_id})
        if doc:
            return int(doc["quantity"])
        # legacy guild-scoped fallback
        doc = await self._db.stock_holdings.find_one(
            {"user_id": int(user_id), "stock_id": stock_id})
        return int(doc["quantity"]) if doc else 0

    async def list_holdings(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> list[dict]:
        if user_id is None and guild_id is not None:
            user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None:
            return []
        cursor = self._db.stock_holdings.find(
            {"user_id": int(user_id), "quantity": {"$gt": 0}})
        return await cursor.to_list(length=200)

    async def list_holders(self, stock_id: str) -> list[dict]:
        cursor = self._db.stock_holdings.find({"stock_id": stock_id, "quantity": {"$gt": 0}})
        return await cursor.to_list(length=1000)

    async def adjust_holding(self, guild_id: int | None = None, user_id: int | None = None, stock_id: str | None = None, delta: int | None = None, *args, **kwargs) -> int:
        # Normalize args: support (user_id, stock_id, delta) and (guild_id, user_id, stock_id, delta)
        if delta is None:
            if stock_id is not None and user_id is not None:
                # 3-arg call: guild_id=user_id, user_id=stock_id, stock_id=delta
                if isinstance(stock_id, int):
                    delta = int(stock_id)
                    stock_id = str(user_id)
                    user_id = guild_id  # type: ignore
                else:
                    delta = kwargs.get("delta", 0)
            else:
                delta = kwargs.get("delta", 0)
                if stock_id is None:
                    stock_id = kwargs.get("stock_id")
                if user_id is None:
                    user_id = kwargs.get("user_id") or guild_id  # type: ignore
        if user_id is None or stock_id is None or delta is None:
            raise ValueError("user_id, stock_id, delta required")
        doc = await self._db.stock_holdings.find_one(
            {"user_id": int(user_id), "stock_id": stock_id})
        new_qty = (int(doc["quantity"]) if doc else 0) + int(delta)
        if new_qty < 0:
            raise ValueError("holdings cannot go negative")
        if new_qty == 0:
            await self._db.stock_holdings.delete_one(
                {"user_id": int(user_id), "stock_id": stock_id})
        else:
            await self._db.stock_holdings.update_one(
                {"user_id": int(user_id), "stock_id": stock_id},
                {"$set": {"quantity": new_qty}}, upsert=True)
        return new_qty

    # -- trades / prices / activity --
    async def insert_trade(self, doc: dict) -> str:
        doc = dict(doc)
        doc["guild_id"] = 0
        res = await self._db.stock_trades.insert_one(doc)
        return str(res.inserted_id)

    async def list_trades(self, guild_id: int | None = None, stock_id: str | None = None,
                          user_id: int | None = None, limit: int = 20, *args, **kwargs) -> list[dict]:
        # guild_id ignored – global
        filt: dict = {}
        if stock_id is not None:
            filt["stock_id"] = stock_id
        if user_id is not None:
            filt["user_id"] = user_id
        cursor = self._db.stock_trades.find(filt).sort("ts", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def insert_price_event(self, doc: dict) -> str:
        doc = dict(doc)
        doc["guild_id"] = 0
        res = await self._db.stock_prices.insert_one(doc)
        return str(res.inserted_id)

    async def list_price_history(self, stock_id: str, limit: int = 100) -> list[dict]:
        cursor = self._db.stock_prices.find({"stock_id": stock_id}).sort("ts", 1).limit(limit)
        return await cursor.to_list(length=limit)

    async def record_activity(self, doc: dict) -> None:
        doc = dict(doc)
        doc["guild_id"] = 0
        await self._db.stock_activity.insert_one(doc)

    async def activity_since(self, stock_id: str, since_ts: float) -> list[dict]:
        cursor = self._db.stock_activity.find({"stock_id": stock_id, "ts": {"$gte": since_ts}})
        return await cursor.to_list(length=5000)

    async def last_owner_activity(self, stock_id: str, owner_id: int) -> float | None:
        cursor = self._db.stock_activity.find(
            {"stock_id": stock_id, "user_id": owner_id}).sort("ts", -1).limit(1)
        docs = await cursor.to_list(length=1)
        return float(docs[0]["ts"]) if docs else None

    # -- watchlists / alerts --
    async def watch_add(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, *args, **kwargs) -> None:
        if ticker is None and user_id is not None and isinstance(user_id, str):
            ticker = user_id
            user_id = guild_id  # type: ignore
        if ticker is None:
            ticker = kwargs.get("ticker")
        if user_id is None:
            user_id = kwargs.get("user_id")
            if user_id is None and guild_id is not None and isinstance(guild_id, int):
                user_id = guild_id  # type: ignore
        if user_id is None or ticker is None:
            return
        await self._db.stock_watchlists.update_one(
            {"user_id": int(user_id)},
            {"$addToSet": {"tickers": ticker}}, upsert=True)

    async def watch_remove(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, *args, **kwargs) -> None:
        if ticker is None and user_id is not None and isinstance(user_id, str):
            ticker = user_id
            user_id = guild_id  # type: ignore
        if ticker is None:
            ticker = kwargs.get("ticker")
        if user_id is None:
            user_id = kwargs.get("user_id")
            if user_id is None and guild_id is not None:
                user_id = guild_id  # type: ignore
        if user_id is None or ticker is None:
            return
        await self._db.stock_watchlists.update_one(
            {"user_id": int(user_id)}, {"$pull": {"tickers": ticker}})

    async def watch_list(self, guild_id: int | None = None, user_id: int | None = None, *args, **kwargs) -> list[str]:
        if user_id is None and guild_id is not None:
            user_id = guild_id  # type: ignore
        if user_id is None:
            user_id = kwargs.get("user_id")
        if user_id is None:
            return []
        doc = await self._db.stock_watchlists.find_one(
            {"user_id": int(user_id)})
        return sorted(doc.get("tickers", [])) if doc else []

    async def alert_add(self, guild_id: int | None = None, user_id: int | None = None, ticker: str | None = None, price: float | None = None, *args, **kwargs) -> str:
        if price is None and ticker is not None and isinstance(ticker, (int, float)):
            price = float(ticker)
            ticker = str(user_id)
            user_id = guild_id  # type: ignore
        if price is None:
            price = kwargs.get("price")
        if ticker is None:
            ticker = kwargs.get("ticker")
        if user_id is None:
            user_id = kwargs.get("user_id")
            if user_id is None and guild_id is not None:
                user_id = guild_id  # type: ignore
        res = await self._db.stock_alerts.insert_one({
            "guild_id": 0, "user_id": int(user_id) if user_id is not None else 0, "ticker": ticker,
            "price_minor": int(round(float(price) * 100)) if price is not None else 0, "triggered": False,
            "created_at": time.time(),
        })
        return str(res.inserted_id)

    async def alerts_for_stock(self, guild_id: int | None = None, ticker: str | None = None, *args, **kwargs) -> list[dict]:
        if ticker is None and isinstance(guild_id, str):
            ticker = guild_id
        if ticker is None:
            ticker = kwargs.get("ticker")
        if ticker is None:
            return []
        cursor = self._db.stock_alerts.find(
            {"ticker": ticker, "triggered": False})
        return await cursor.to_list(length=200)

    async def mark_alert_triggered(self, alert_id: str) -> None:
        from bson import ObjectId
        try:
            oid: Any = ObjectId(alert_id)
        except Exception:
            oid = alert_id
        await self._db.stock_alerts.update_one({"_id": oid}, {"$set": {"triggered": True}})
