import statistics

SLAB_RATES = (0.10, 0.08, 0.06, 0.04, 0.02)
SLAB_EDGES = (0.5, 1.0, 2.0, 4.0)
RATE_PERIOD_DAYS = 30

TENURES = {1: 0.5, 3: 0.75, 7: 1.0, 14: 1.2, 30: 1.4}
EARLY_BREAK_PENALTY = 0.2

MIN_FD_AMOUNT = 100_000
MAX_FDS_PER_PLAYER = 3
MAX_TOTAL_IN_MEDIANS = 8.0

SERVER_QUIET_HOURS = 24
PLAYER_QUIET_HOURS = 72
HELD_PENALTY = 0.15
MIN_UNLOCK_TRADE = 100_000

def slab_interest(amount, median):
    r1, r2, r3, r4, r5 = SLAB_RATES
    e1, e2, e3, e4 = (e * median for e in SLAB_EDGES)

    if amount <= e1:
        return r1*amount
    elif amount <= e2:
        return r1*e1 + r2*(amount - e1)
    elif amount <= e3:
        return r1*e1 + r2*(e2 - e1) + r3*(amount - e2)
    elif amount <= e4:
        return r1*e1 + r2*(e2 - e1) + r3*(e3 - e2) + r4*(amount - e3)
    else:
        return r1*e1 + r2*(e2 - e1) + r3*(e3 - e2) + r4*(e4 - e3) + r5*(amount - e4)


def tenure_multiplier(days_held):
    if days_held >= 30:
        return TENURES[30]
    elif days_held >= 14:
        return TENURES[14]
    elif days_held >= 7:
        return TENURES[7]
    elif days_held >= 3:
        return TENURES[3]
    elif days_held >= 1:
        return TENURES[1]
    else:
        return 0.0


async def median_balance(db):
    worth = {}
    for d in await db.stock_balances.find({}, {"user_id": 1, "balance": 1}).to_list(length=None):
        worth[int(d["user_id"])] = int(d.get("balance", 0))
    if not worth:
        return None

    prices = {str(s["_id"]): int(s.get("current_price", 0))
              for s in await db.stock_stocks.find({}, {"current_price": 1}).to_list(length=None)}
    for h in await db.stock_holdings.find({}, {"user_id": 1, "stock_id": 1, "quantity": 1}).to_list(length=None):
        uid = int(h["user_id"])
        if uid in worth:
            worth[uid] += int(h.get("quantity", 0)) * prices.get(str(h["stock_id"]), 0)
    for f in await db.stock_fixed_deposits.find({"status": "active"}, {"user_id": 1, "amount": 1}).to_list(length=None):
        uid = int(f["user_id"])
        if uid in worth:
            worth[uid] += int(f["amount"])

    return statistics.median(worth.values())


async def active_seconds(db, start, end):
    if end <= start:
        return 0.0
    window = SERVER_QUIET_HOURS * 3600
    docs = await db.stock_prices.find(
        {"ts": {"$gte": start - window, "$lte": end}, "reason": "scheduled"},
        {"ts": 1, "components": 1},
    ).to_list(length=None)
    chatty = sorted(
        float(d["ts"]) for d in docs
        if float((d.get("components") or {}).get("owner", 0.0))
        + float((d.get("components") or {}).get("holder", 0.0)) > 0
    )

    total = 0.0
    covered_to = start
    for ts in chatty:
        seg_start, seg_end = max(ts, covered_to), min(ts + window, end)
        if seg_end > seg_start:
            total += seg_end - seg_start
            covered_to = seg_end
    return total


async def player_quiet(db, user_id, now):
    trade = await db.stock_trades.find_one({
        "user_id": int(user_id),
        "ts": {"$gte": now - PLAYER_QUIET_HOURS * 3600},
        "gross": {"$gte": MIN_UNLOCK_TRADE},
    })
    return trade is None
