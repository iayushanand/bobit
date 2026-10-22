"""Aggregation for charts and stats (no plotting here)."""


def price_series(history: list[dict]) -> tuple[list[float], list[float]]:
    """Sorted (timestamps, prices_minor) from price events."""
    ordered = sorted(history, key=lambda p: float(p.get("ts", 0)))
    return ([float(p.get("ts", 0)) for p in ordered],
            [float(p.get("price", 0)) for p in ordered])


def summarize(history: list[dict]) -> dict:
    """High/low/change/volatility over a history window."""
    _, prices = price_series(history)
    if not prices:
        return {"points": 0, "change": 0.0, "change_pct": 0.0,
                "high": 0.0, "low": 0.0, "volatility": 0.0}
    first, last = prices[0], prices[-1]
    change = last - first
    import statistics as _s
    vol = _s.pstdev(prices) if len(prices) > 1 else 0.0
    return {"points": len(prices), "change": change,
            "change_pct": (change / first) if first else 0.0,
            "high": max(prices), "low": min(prices), "volatility": vol}


def volume_series(trades: list[dict]) -> tuple[list[float], list[float]]:
    """(timestamps, quantities) sorted."""
    ordered = sorted(trades, key=lambda t: float(t.get("ts", 0)))
    return ([float(t.get("ts", 0)) for t in ordered],
            [float(t.get("quantity", 0)) for t in ordered])


def volumes_per_interval(price_ts: list[float], trades: list[dict]) -> list[float]:
    """Bucket trade quantities into price-point intervals.

    Trade at time ``t`` counts toward the latest price point with
    ``ts <= t`` (or the first point if earlier). Returns one volume per
    price timestamp; pure helper for the volume bar panel.
    """
    volumes = [0.0] * len(price_ts)
    if not price_ts:
        return volumes
    order = sorted(range(len(price_ts)), key=lambda i: price_ts[i])
    for trade in trades:
        t = float(trade.get("ts", 0))
        qty = float(trade.get("quantity", 0))
        slot = order[0]
        for i in order:
            if price_ts[i] <= t:
                slot = i
            else:
                break
        volumes[slot] += qty
    return volumes


def candles(price_ts: list[float], prices: list[float],
            volumes: list[float] | None = None, max_candles: int = 30) -> list[dict]:
    """Resample ordered points into up to ``max_candles`` OHLC candles.

    Each candle covers a consecutive run of points: open is the first,
    close the last, high/low the extremes, ts the last point's time,
    volume the summed per-point volumes. Pure helper for candlesticks.
    """
    import math

    if not price_ts or not prices or len(price_ts) != len(prices):
        return []
    vols = list(volumes) if volumes and len(volumes) == len(prices) else [0.0] * len(prices)
    order = sorted(range(len(price_ts)), key=lambda i: price_ts[i])
    size = max(1, math.ceil(len(order) / max(1, max_candles)))
    out = []
    for start in range(0, len(order), size):
        idx = order[start:start + size]
        pts = [prices[i] for i in idx]
        out.append({"ts": price_ts[idx[-1]], "open": pts[0], "high": max(pts),
                    "low": min(pts), "close": pts[-1],
                    "volume": sum(vols[i] for i in idx)})
    return out


def side_volumes(price_ts: list[float], trades: list[dict] | None,
                 max_candles: int = 30) -> tuple[list[float], list[float]]:
    """Buy/sell quantities per candle bucket, aligned with ``candles()``.

    Each trade counts toward the candle holding the latest price point
    with ``ts <= trade_ts``. Returns ``(buys, sells)`` with one entry
    per candle; a trade with ``side == "sell"`` counts as a sell,
    anything else as a buy. Pure helper for the buy/sell bar panel.
    """
    import math

    if not price_ts:
        return [], []
    order = sorted(range(len(price_ts)), key=lambda i: price_ts[i])
    size = max(1, math.ceil(len(order) / max(1, max_candles)))
    chunks: list[list[int]] = [order[start:start + size] for start in range(0, len(order), size)]
    chunk_of = {i: pos for pos, chunk in enumerate(chunks) for i in chunk}
    buys = [0.0] * len(chunks)
    sells = [0.0] * len(chunks)
    for trade in trades or []:
        t = float(trade.get("ts", 0))
        qty = float(trade.get("quantity", 0))
        slot = order[0]
        for i in order:
            if price_ts[i] <= t:
                slot = i
            else:
                break
        if str(trade.get("side", "buy")).lower() == "sell":
            sells[chunk_of[slot]] += qty
        else:
            buys[chunk_of[slot]] += qty
    return buys, sells


def allocation(positions: list[dict], top_n: int = 5) -> list[dict]:
    """Top holdings + grouped 'Other' for pie charts."""
    ordered = sorted(positions, key=lambda p: p["value"], reverse=True)
    if len(ordered) <= top_n:
        return ordered
    head = ordered[:top_n]
    rest = sum(p["value"] for p in ordered[top_n:])
    return head + [{"ticker": "Other", "name": "Other", "quantity": 0,
                    "price": 0, "value": rest}]


def movers(stocks: list[dict], history_by_stock: dict[str, list[dict]],
           limit: int = 5) -> tuple[list[dict], list[dict]]:
    """Top gainers and losers by change_pct over the given histories."""
    ranked = []
    for s in stocks:
        sid = str(s["_id"])
        summary = summarize(history_by_stock.get(sid, []))
        ranked.append({"ticker": s["ticker"], "change_pct": summary["change_pct"],
                       "price": s.get("current_price", 0)})
    ranked.sort(key=lambda r: r["change_pct"], reverse=True)
    return ranked[:limit], list(reversed(ranked[-limit:]))
