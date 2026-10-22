"""Scheduled price updates: activity aggregation + time-based decay.

- Never updates prices per message; this loop runs every
  ``price_update_interval_minutes`` (default 10).
- Trade impact is NOT re-applied here (trades settle immediately in
  the service layer). This loop handles owner/holder/inactivity/baseline.
- Restart-safe: elapsed time comes from ``last_price_update_at``; a long
  downtime yields one bounded move (clamped), never repeated compounding.
"""

import random
import time

from .activity import count_events
from .pricing import (
    baseline_return,
    combine_returns,
    holder_aggregate_score,
    holder_activity_return,
    inactivity_decay_return,
    normalize_score,
    owner_activity_return,
)


async def update_one_stock(repo, stock: dict, config, now: float | None = None,
                           rand: random.Random | None = None) -> dict | None:
    """Apply one scheduled update to a single stock. Returns price event."""
    now = time.time() if now is None else now
    rnd = rand or random
    stock_id = str(stock["_id"])
    owner_id = int(stock["owner_user_id"])
    last_update = float(stock.get("last_price_update_at", now))
    elapsed = max(0.0, now - last_update)

    window_start = now - config.activity_window_seconds
    events = await repo.activity_since(stock_id, window_start)
    counts = count_events(events)
    owner_count = int(counts.get(owner_id, 0))
    holder_counts = [c for u, c in counts.items() if u != owner_id]

    owner_score = normalize_score(owner_count, config.owner_activity_target)
    holder_score = holder_aggregate_score(holder_counts, config.holder_per_member_cap,
                                          config.holder_activity_target)

    last_owner_ts = await repo.last_owner_activity(stock_id, owner_id)
    if last_owner_ts is None:
        last_owner_ts = float(stock.get("last_owner_activity_at",
                                        stock.get("created_at", now)))
    hours_since_owner = (now - last_owner_ts) / 3600.0
    # Holder freshness: use most recent holder event, else stale.
    holder_ts = [e["ts"] for e in events if int(e["user_id"]) != owner_id]
    hours_since_holder = ((now - max(holder_ts)) / 3600.0) if holder_ts else None

    owner_comp = owner_activity_return(owner_score, hours_since_owner,
                                       config.owner_max_return, config.stale_horizon_hours)
    holder_comp = holder_activity_return(holder_score, hours_since_holder,
                                         config.holder_max_return, config.stale_horizon_hours)
    decay_comp = inactivity_decay_return(elapsed, config.inactivity_decay_per_day)
    base_comp = baseline_return(rnd.uniform(-1.0, 1.0), config.baseline_vol)

    breakdown = combine_returns(
        int(stock["current_price"]), owner_comp, holder_comp, decay_comp,
        0.0, base_comp, config.max_scheduled_move,
        config.min_price_minor, config.max_price_minor,
    )
    await repo.update_stock(stock_id, {
        "current_price": breakdown.new_price_minor,
        "liquidity": max(config.minimum_liquidity_minor,
                         breakdown.new_price_minor * int(stock.get("available_shares", 0))),
        "last_price_update_at": now,
    })
    event = {
        "stock_id": stock_id, "guild_id": 0, "ts": now,
        "price": breakdown.new_price_minor, "reason": "scheduled",
        "components": {"owner": owner_comp, "holder": holder_comp,
                       "inactivity": decay_comp, "trade": 0.0, "baseline": base_comp},
        "return": breakdown.clamped_return,
    }
    await repo.insert_price_event(event)
    await check_alerts(repo, stock, breakdown.new_price_minor)
    return event


async def check_alerts(repo, stock: dict, new_price_minor: int) -> list[dict]:
    """Mark crossed alerts as triggered; caller DMs the users."""
    triggered = []
    for alert in await repo.alerts_for_stock(0, stock["ticker"]):
        if int(new_price_minor) >= int(alert["price_minor"]):
            await repo.mark_alert_triggered(str(alert["_id"]))
            triggered.append(alert)
    # also try without guild arg
    if not triggered:
        try:
            for alert in await repo.alerts_for_stock(stock["ticker"]):  # type: ignore
                if int(new_price_minor) >= int(alert["price_minor"]) and alert not in triggered:
                    await repo.mark_alert_triggered(str(alert["_id"]))
                    triggered.append(alert)
        except Exception:
            pass
    return triggered


async def run_market_update(repo, config, guild_id: int | None = None,
                            rand: random.Random | None = None) -> list[dict]:
    """Update all active stocks (global). ``guild_id`` is ignored for backwards compat."""
    now = time.time()
    # Global – ignore guild_id, update all active stocks
    if hasattr(repo, "stocks"):
        stocks = [d for d in repo.stocks.values() if d.get("status") == "active"]
        if stocks:
            pass
        else:
            # fall through to repo query
            stocks = await repo.list_active_stocks(None)
    else:
        stocks = await repo.list_active_stocks(guild_id)
    events = []
    for stock in stocks:
        try:
            event = await update_one_stock(repo, stock, config, now, rand)
            if event:
                events.append(event)
        except Exception:
            continue
    return events
