"""Stock market commands (prefix `.stock`)."""

import asyncio
import time

import discord
from discord.ext import commands, tasks

from utils.bot import BoBit
from utils.consts import Colors

from .activity import ActivityTracker
try:
    from .charts import allocation_chart, movers_chart, price_chart
    CHARTS_AVAILABLE = True
except ImportError:  # matplotlib missing -> text-only mode, cog still loads
    allocation_chart = movers_chart = price_chart = None  # type: ignore
    CHARTS_AVAILABLE = False
from .config import DEFAULT_CONFIG, StockConfig, format_cash
from .exceptions import StockError
from .market_tasks import run_market_update
from .repository import InMemoryRepository, MongoRepository
from .service import StockService
from .statistics import allocation, movers, price_series, summarize
from .validators import normalize_ticker, validate_quantity


def _err_embed(message: str) -> discord.Embed:
    return discord.Embed(title="Stock error", description=message, color=Colors.RED)


TWO_DAYS = 2 * 86400


def _recent_history(history: list[dict]) -> list[dict]:
    cutoff = time.time() - TWO_DAYS
    return [h for h in history if float(h.get("ts", 0)) >= cutoff]


def _ok_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=Colors.GREEN)


class Stock(commands.Cog):

    def __init__(self, bot: BoBit, config: StockConfig = DEFAULT_CONFIG) -> None:
        self.bot = bot
        self.config = config
        self._updating = False
        self.tracker = ActivityTracker(config.scoring_cooldown_seconds)
        self._repo = None
        self._service = None

    @property
    def repo(self):
        if self._repo is None:
            if getattr(self.bot.db, "stock_stocks", None) is not None:
                self._repo = MongoRepository(self.bot.db)
            else:  # fallback (tests / no DB)
                self._repo = InMemoryRepository()
        return self._repo

    @property
    def service(self) -> StockService:
        if self._service is None:
            self._service = StockService(self.repo, self.config)
        return self._service

    async def cog_load(self) -> None:
        try:
            await self.repo.ensure_indexes()
        except Exception:
            pass
        if not self.market_loop.is_running():
            self.market_loop.start()

    async def cog_before_invoke(self, ctx: commands.Context) -> None:
        # ensure caller has a stock account (100k starting balance) for any stock command
        if ctx.command and ctx.command.qualified_name.startswith("stock"):
            try:
                await self.service.balance_of(None, ctx.author.id)
            except Exception:
                pass

    async def cog_unload(self) -> None:
        if self.market_loop.is_running():
            self.market_loop.cancel()

    # -- scheduled pricing -- global single update
    @tasks.loop(minutes=DEFAULT_CONFIG.price_update_interval_minutes)
    async def market_loop(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            try:
                await run_market_update(self.repo, self.config, None)
            except Exception:
                pass
        finally:
            self._updating = False

    @market_loop.before_loop
    async def _before_market_loop(self) -> None:
        await self.bot.wait_until_ready()

    # -- activity listener (cheap path; scoring happens in the loop) -- global
    @commands.Cog.listener("on_message")
    async def activity_listener(self, message: discord.Message) -> None:
        if not self.tracker.is_qualifying_message(
            message.content or "",
            message.author.bot,
            bool(getattr(message, "webhook_id", None)),
            message.channel.id,
            tuple(self.config.excluded_channel_ids),
            tuple(self.config.command_prefixes),
        ):
            return
        if not self.tracker.check_cooldown(message.author.id):
            return
        try:
            user_id = message.author.id
            stocks = await self.repo.list_all_stocks()
            owned_ids = {str(s["_id"]) for s in stocks
                         if int(s.get("owner_user_id", -1)) == user_id}
            holdings = await self.repo.list_holdings(None, user_id)
            held_ids = {h["stock_id"] for h in holdings}
            now = time.time()
            for sid in owned_ids | held_ids:
                role = "owner" if sid in owned_ids else "holder"
                await self.repo.record_activity({
                    "stock_id": sid, "guild_id": 0,
                    "user_id": user_id, "role": role, "ts": now,
                })
        except Exception:
            return

    # -- error handling --
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, StockError):
            await ctx.send(embed=_err_embed(str(original)))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=_err_embed(f"Slow down — retry in {error.retry_after:.0f}s."))
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=_err_embed("Invalid argument."))

    # -- group --
    @commands.group(name="stock", aliases=["stocks", "stks"], invoke_without_command=True)
    async def stock(self, ctx: commands.Context) -> None:
        await ctx.send(embed=self._help_embed())

    def _help_embed(self) -> discord.Embed:
        e = discord.Embed(
            title="Stocks",
            description="`.stock create` · `.stock buy` · `.stock sell` · `.stock portfolio` · `.stock info` · `.stock market`",
            color=Colors.BLURPLE,
        )
        return e

    async def _price_chart_file(self, doc: dict, force_line: bool = False) -> discord.File | None:
        """Render the price + buy/sell chart; None if unavailable/failed/too few points."""
        if not CHARTS_AVAILABLE:
            return None
        try:
            history = await self.repo.list_price_history(str(doc["_id"]), limit=500)
            history = _recent_history(history)
            ts, prices = price_series(history)
            if len(prices) < 2:
                return None
            trades = await self.repo.list_trades(None, str(doc["_id"]), None, 200)
            # keep only recent trades for the 2-day window
            cutoff = time.time() - TWO_DAYS
            trades = [t for t in trades if float(t.get("ts", 0)) >= cutoff]
            buf = await asyncio.to_thread(price_chart, ts, prices, doc["ticker"],
                                          self.config.currency_symbol, trades, force_line)
        except Exception:
            return None
        return discord.File(buf, filename=f"{doc['ticker']}_chart.png")

    @stock.command(name="help", aliases=["h", "commands"])
    async def stock_help(self, ctx: commands.Context) -> None:
        await ctx.send(embed=self._help_embed())

    # -- create / info / market --
    @stock.command(name="create", aliases=["new", "add", "make"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def stock_create(self, ctx: commands.Context, ticker: str, name: str,
                           *, description: str = "") -> None:
        try:
            doc = await self.service.create_stock(None, ctx.author.id, ticker, name, description)
        except StockError as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        e = _ok_embed(f"Created `{doc['ticker']}` — {doc['name']}",
                      f"{format_cash(doc['current_price'], self.config)} · {doc['total_shares']:,} shares")
        await ctx.send(embed=e)

    @stock.command(name="info", aliases=["i", "show", "view"])
    async def stock_info(self, ctx: commands.Context, ticker: str) -> None:
        try:
            doc = await self.service.require_stock(None, ticker)
        except StockError as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        history = await self.repo.list_price_history(str(doc["_id"]), limit=500)
        history = _recent_history(history)
        summary = summarize(history)
        e = discord.Embed(title=f"{doc['ticker']} — {doc.get('name', '')}",
                          description=(doc.get("description") or "")[:200],
                          color=Colors.DARK_EMBED)
        e.add_field(name="Price", value=format_cash(int(doc["current_price"]), self.config))
        e.add_field(name="Supply", value=f"{doc.get('available_shares', 0):,} / {doc.get('total_shares', 0):,}")
        e.add_field(name="Change", value=f"{summary['change_pct'] * 100:+.2f}%")
        chart = await self._price_chart_file(doc, force_line=True)
        if chart is not None:
            e.set_image(url=f"attachment://{chart.filename}")
            await ctx.send(embed=e, file=chart)
        else:
            await ctx.send(embed=e)

    @stock.command(name="market", aliases=["list", "all", "overview"])
    async def stock_market(self, ctx: commands.Context) -> None:
        stocks = await self.service.market_overview(None)
        if not stocks:
            await ctx.send(embed=discord.Embed(title="Market",
                                               description="No stocks yet. `.stock create TICKER Name`",
                                               color=Colors.DARK_EMBED))
            return
        lines = [f"**{s['ticker']}** {s.get('name', '')} — "
                 f"{format_cash(int(s['current_price']), self.config)} "
                 f"({s.get('available_shares', 0):,} avail)" for s in stocks[:20]]
        await ctx.send(embed=discord.Embed(title="Market", description="\n".join(lines),
                                           color=Colors.DARK_EMBED))

    # -- trading --
    @stock.command(name="buy", aliases=["b", "purchase", "pump"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def stock_buy(self, ctx: commands.Context, ticker: str, quantity: int) -> None:
        try:
            receipt = await self.service.buy(None, ctx.author.id, ticker, int(quantity))
        except (StockError, ValueError) as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        e = _ok_embed(f"Bought {receipt.quantity} {receipt.ticker}",
                      f"@ {format_cash(receipt.execution_price_minor, self.config)} · "
                      f"Total {format_cash(receipt.total_minor, self.config)}")
        await ctx.send(embed=e)

    @stock.command(name="sell", aliases=["s", "dump"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def stock_sell(self, ctx: commands.Context, ticker: str, quantity: int) -> None:
        try:
            receipt = await self.service.sell(None, ctx.author.id, ticker, int(quantity))
        except (StockError, ValueError) as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        e = _ok_embed(f"Sold {receipt.quantity} {receipt.ticker}",
                      f"@ {format_cash(receipt.execution_price_minor, self.config)} · "
                      f"Total {format_cash(receipt.total_minor, self.config)}")
        await ctx.send(embed=e)

    @stock.command(name="portfolio", aliases=["pf", "p", "port", "holdings", "inv"])
    async def stock_portfolio(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        data = await self.service.portfolio(None, target.id)
        lines = [f"**{p['ticker']}** ×{p['quantity']:,} @ "
                 f"{format_cash(p['price'], self.config)} = {format_cash(p['value'], self.config)}"
                 for p in data["positions"][:20]]
        e = discord.Embed(title=f"{target.display_name}'s portfolio",
                          description="\n".join(lines) if lines else "No holdings yet.",
                          color=Colors.DARK_EMBED)
        e.add_field(name="Cash", value=format_cash(data["balance"], self.config))
        e.add_field(name="Holdings", value=format_cash(data["holdings_value"], self.config))
        chart_file = None
        if CHARTS_AVAILABLE and len(data["positions"]) > 1:
            try:
                alloc = allocation(data["positions"])
                buf = await asyncio.to_thread(
                    allocation_chart, [a["ticker"] for a in alloc], [a["value"] for a in alloc],
                    f"{target.display_name} allocation")
                chart_file = discord.File(buf, filename="allocation.png")
                e.set_image(url="attachment://allocation.png")
            except Exception:
                chart_file = None
        if chart_file:
            await ctx.send(embed=e, file=chart_file)
        else:
            await ctx.send(embed=e)

    @stock.command(name="balance", aliases=["bal", "cash", "wallet", "money", "funds"])
    async def stock_balance(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        bal = await self.service.balance_of(None, target.id)
        await ctx.send(embed=discord.Embed(title=f"{target.display_name} - Balance",
                                           description=format_cash(bal, self.config),
                                           color=Colors.DARK_EMBED))

    @stock.command(name="pay", aliases=["give", "send", "transfer", "tip"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def stock_pay(self, ctx: commands.Context, member: discord.Member, amount: float) -> None:
        if member.bot:
            await ctx.send(embed=_err_embed("You cannot pay a bot."))
            return
        if member.id == ctx.author.id:
            await ctx.send(embed=_err_embed("You cannot pay yourself."))
            return
        try:
            amount_minor = int(round(float(amount) * 100))
        except Exception:
            await ctx.send(embed=_err_embed("Invalid amount."))
            return
        if amount_minor <= 0:
            await ctx.send(embed=_err_embed("Amount must be positive."))
            return
        giver_bal = await self.service.balance_of(None, ctx.author.id)
        if giver_bal < amount_minor:
            await ctx.send(embed=_err_embed(f"Insufficient funds. You have {format_cash(giver_bal, self.config)}."))
            return
        receiver_bal = await self.service.balance_of(None, member.id)
        await self.repo.set_balance(None, ctx.author.id, giver_bal - amount_minor)
        await self.repo.set_balance(None, member.id, receiver_bal + amount_minor)
        e = discord.Embed(title="Payment sent", description=f"{ctx.author.mention} → {member.mention} — {format_cash(amount_minor, self.config)}", color=Colors.GREEN)
        e.add_field(name="Your balance", value=format_cash(giver_bal - amount_minor, self.config))
        await ctx.send(embed=e)

    @stock.command(name="history", aliases=["hist", "log"])
    async def stock_history(self, ctx: commands.Context, ticker: str, limit: int = 10) -> None:
        try:
            doc = await self.service.require_stock(None, ticker)
        except StockError as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        limit = max(1, min(int(limit), 25))
        trades = await self.repo.list_trades(None, str(doc["_id"]), None, 100)
        cutoff = time.time() - TWO_DAYS
        trades = [t for t in trades if float(t.get("ts", 0)) >= cutoff][:limit]
        if not trades:
            await ctx.send(embed=discord.Embed(title=f"{doc['ticker']} history",
                                               description="No trades in past 2 days.", color=Colors.DARK_EMBED))
            return
        lines = [f"{'<t:' + str(int(t['ts'])) + ':R>'} **{t['side']}** ×{t['quantity']} @ "
                 f"{format_cash(t['price'], self.config)}" for t in trades]
        e = discord.Embed(title=f"{doc['ticker']} history",
                          description="\n".join(lines), color=Colors.DARK_EMBED)
        chart = await self._price_chart_file(doc)
        if chart is not None:
            e.set_image(url=f"attachment://{chart.filename}")
            await ctx.send(embed=e, file=chart)
        else:
            await ctx.send(embed=e)

    @stock.command(name="trades", aliases=["mytrades", "tx", "t"])
    async def stock_trades(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        trades = await self.repo.list_trades(None, None, target.id, 15)
        lines = [f"{t.get('ticker', '') or ''} **{t['side']}** ×{t['quantity']}" for t in trades]
        await ctx.send(embed=discord.Embed(
            title=f"{target.display_name}'s trades",
            description="\n".join(lines) if lines else "No trades yet.",
            color=Colors.DARK_EMBED))

    @stock.command(name="tradelog", aliases=["tlog", "tl", "txlog"])
    async def stock_tradelog(self, ctx: commands.Context, *args) -> None:
        """Trade log for an individual — ` .stock tradelog [TICKER] [@user]` (order independent, shows last 15)"""
        # flexible parse: any arg that converts to Member is member, first non-member string is ticker
        ticker_str: str | None = None
        target: discord.Member | None = None
        for arg in args:
            # try member conversion
            try:
                m = await commands.MemberConverter().convert(ctx, arg)
                if target is None:
                    target = m
                    continue
            except Exception:
                pass
            # numeric limit ignored; first non-member string is ticker
            if ticker_str is None and not arg.isdigit():
                # strip mention-like remnants
                if not arg.startswith("<@"):
                    ticker_str = arg
            elif ticker_str is None and arg.startswith("<@"):
                # already handled as member, ignore
                pass
        # fallback to mentions in message (handles nick mentions not caught)
        if target is None and ctx.message.mentions:
            target = ctx.message.mentions[0]
        if target is None:
            target = ctx.author  # type: ignore

        stock_id: str | None = None
        resolved_ticker: str | None = None
        resolved_name: str | None = None
        if ticker_str:
            try:
                doc = await self.service.require_stock(None, ticker_str)
                stock_id = str(doc["_id"])
                resolved_ticker = doc["ticker"]
                resolved_name = doc.get("name", "")
            except StockError as exc:
                await ctx.send(embed=_err_embed(str(exc)))
                return

        trades = await self.repo.list_trades(None, stock_id, target.id, 20)

        if not trades:
            title = f"{target.display_name}'s trade log" + (f" — {resolved_ticker} — {resolved_name}" if resolved_ticker else "")
            await ctx.send(embed=discord.Embed(title=title, description="No trades yet.", color=Colors.DARK_EMBED))
            return

        # cache stock docs for name lookup when showing multiple tickers
        stock_cache: dict[str, dict] = {}
        if resolved_ticker and resolved_name is not None:
            stock_cache[stock_id or ""] = {"ticker": resolved_ticker, "name": resolved_name}

        lines: list[str] = []
        for t in trades[:15]:
            ts = int(float(t.get("ts", 0)))
            side = str(t.get("side", "buy")).upper()
            qty = t.get("quantity", 0)
            price = int(t.get("price", 0)) if t.get("price") is not None else 0
            price_str = format_cash(price, self.config) if price else ""
            sid = str(t.get("stock_id", ""))
            # resolve ticker + name
            if sid in stock_cache:
                info = stock_cache[sid]
            elif resolved_ticker:
                info = {"ticker": resolved_ticker, "name": resolved_name or ""}
            else:
                # lookup stock for name (cached)
                doc2 = stock_cache.get(sid)
                if doc2 is None:
                    try:
                        doc2 = await self.repo.find_stock_by_id(sid)
                    except Exception:
                        doc2 = None
                    if doc2:
                        stock_cache[sid] = doc2
                info = doc2 or {"ticker": t.get("ticker") or sid[:6], "name": ""}  # type: ignore
            ticker_label = info.get("ticker") or sid[:6]
            name_label = info.get("name") or ""
            label = f"{ticker_label} — {name_label}" if name_label else ticker_label
            lines.append(f"<t:{ts}:R> **{side}** {label} ×{qty} @ {price_str}")

        title = f"{target.display_name}'s trade log" + (f" — {resolved_ticker} — {resolved_name}" if resolved_ticker else "")
        e = discord.Embed(title=title, description="\n".join(lines), color=Colors.DARK_EMBED)
        e.set_footer(text=f"Showing {len(lines)} of {len(trades)}")
        await ctx.send(embed=e)

    # -- charts / stats / leaderboard --
    @stock.command(name="chart", aliases=["c", "graph", "g"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def stock_chart(self, ctx: commands.Context, ticker: str) -> None:
        try:
            doc = await self.service.require_stock(None, ticker)
        except StockError as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        history = await self.repo.list_price_history(str(doc["_id"]), limit=500)
        history = _recent_history(history)
        ts, prices = price_series(history)
        if len(ts) < 2:
            await ctx.send(embed=_err_embed("Not enough recent history (need 2 points from past 2 days)."))
            return
        if not CHARTS_AVAILABLE:
            await ctx.send(embed=discord.Embed(
                title=f"{doc['ticker']}",
                description="Chart rendering unavailable (missing optional dependency). "
                            f"Current price {format_cash(int(doc['current_price']), self.config)}.",
                color=Colors.DARK_EMBED))
            return
        try:
            trades = await self.repo.list_trades(None, str(doc["_id"]), None, 200)
            cutoff = time.time() - TWO_DAYS
            trades = [t for t in trades if float(t.get("ts", 0)) >= cutoff]
            buf = await asyncio.to_thread(price_chart, ts, prices, doc["ticker"],
                                          self.config.currency_symbol, trades, True)
        except Exception:
            await ctx.send(embed=_err_embed("Chart rendering failed; try again later."))
            return
        e = discord.Embed(title=f"{doc['ticker']} chart", description=f"Current {format_cash(int(doc['current_price']), self.config)}", color=Colors.DARK_EMBED)
        chart_file = discord.File(buf, filename=f"{doc['ticker']}_chart.png")
        e.set_image(url=f"attachment://{chart_file.filename}")
        await ctx.send(embed=e, file=chart_file)

    @stock.command(name="stats", aliases=["st", "stat", "statistics"])
    async def stock_stats(self, ctx: commands.Context, ticker: str) -> None:
        try:
            doc = await self.service.require_stock(None, ticker)
        except StockError as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        history = await self.repo.list_price_history(str(doc["_id"]), limit=500)
        history = _recent_history(history)
        summary = summarize(history)
        e = discord.Embed(title=f"{doc['ticker']} stats", color=Colors.DARK_EMBED)
        e.add_field(name="Current", value=format_cash(int(doc["current_price"]), self.config))
        e.add_field(name="Change", value=f"{summary['change_pct'] * 100:+.2f}%")
        e.add_field(name="High/Low", value=f"{format_cash(int(summary['high']), self.config)} / "
                                           f"{format_cash(int(summary['low']), self.config)}")
        e.add_field(name="Points", value=str(summary["points"]))
        await ctx.send(embed=e)

    @stock.command(name="leaderboard", aliases=["lb", "top", "rank", "leaders", "ranking"])
    async def stock_leaderboard(self, ctx: commands.Context) -> None:
        stocks = await self.service.market_overview(None)
        if not stocks:
            await ctx.send(embed=_err_embed("No stocks yet."))
            return
        worth: dict[int, int] = {}
        for s in stocks:
            for h in await self.repo.list_holders(str(s["_id"])):
                worth[h["user_id"]] = worth.get(h["user_id"], 0) + h["quantity"] * int(s["current_price"])
        if not worth:
            await ctx.send(embed=_err_embed("No holders yet."))
            return
        ranked = sorted(worth.items(), key=lambda kv: kv[1], reverse=True)[:10]
        lines = [f"<@{uid}> — {format_cash(val, self.config)} (est.)" for uid, val in ranked]
        e = discord.Embed(title="Leaderboard", description="\n".join(lines), color=Colors.GOLD)
        chart_file = None
        if CHARTS_AVAILABLE:
            try:
                history_by = {str(s["_id"]): await self.repo.list_price_history(str(s["_id"]), 100)
                              for s in stocks[:10]}
                # filter to 2-day for movers consistency
                for sid in list(history_by.keys()):
                    history_by[sid] = _recent_history(history_by[sid])
                gainers, _ = movers(stocks[:10], history_by, limit=5)
                if gainers:
                    buf = await asyncio.to_thread(
                        movers_chart, [g["ticker"] for g in gainers],
                        [g["change_pct"] for g in gainers], "Top movers %")
                    chart_file = discord.File(buf, filename="movers.png")
                    e.set_image(url="attachment://movers.png")
            except Exception:
                chart_file = None
        if chart_file:
            await ctx.send(embed=e, file=chart_file)
        else:
            await ctx.send(embed=e)

    # -- watchlist / alerts --
    @stock.command(name="watch", aliases=["w", "follow", "track"])
    async def stock_watch(self, ctx: commands.Context, ticker: str) -> None:
        try:
            doc = await self.service.require_stock(None, ticker)
        except StockError as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        await self.repo.watch_add(None, ctx.author.id, doc["ticker"])
        await ctx.send(embed=_ok_embed(f"Watching `{doc['ticker']}`"))

    @stock.command(name="unwatch", aliases=["uw", "unfollow", "untrack", "rm"])
    async def stock_unwatch(self, ctx: commands.Context, ticker: str) -> None:
        await self.repo.watch_remove(None, ctx.author.id, normalize_ticker(ticker))
        await ctx.send(embed=_ok_embed("Removed from watchlist"))

    @stock.command(name="alert", aliases=["a", "notify", "pricealert"])
    async def stock_alert(self, ctx: commands.Context, ticker: str, price: float) -> None:
        try:
            doc = await self.service.require_stock(None, ticker)
            await self.repo.alert_add(None, ctx.author.id, doc["ticker"], float(price))
        except (StockError, ValueError) as exc:
            await ctx.send(embed=_err_embed(str(exc)))
            return
        await ctx.send(embed=_ok_embed(f"Alert set for `{doc['ticker']}` at {price}"))


async def setup(bot: BoBit) -> None:
    await bot.add_cog(Stock(bot))
