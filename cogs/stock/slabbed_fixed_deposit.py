import statistics
import time

from .exceptions import InsufficientFundsError, LimitError, NotFoundError

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

DAY = 86_400


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


async def _list(db, user_id, status):
    docs = await db.stock_fixed_deposits.find(
        {"user_id": int(user_id), "status": status}
    ).to_list(length=None)
    return sorted(docs, key=lambda d: d["opened_at"])


async def _credit(db, user_id, amount):
    if amount > 0:
        await db.stock_balances.update_one({"user_id": int(user_id)}, {"$inc": {"balance": int(amount)}})


async def _close(db, fd, status, interest, now):
    res = await db.stock_fixed_deposits.update_one(
        {"_id": fd["_id"], "status": "active"},
        {"$set": {"status": status, "interest": interest, "closed_at": now}},
    )
    return res.modified_count == 1


async def _pay_out(db, fd, interest, status, quiet_player, now):
    if quiet_player and interest > 0:
        if await _close(db, fd, "held", interest, now):
            await db.stock_fixed_deposits.update_one({"_id": fd["_id"]}, {"$set": {"held_from": status}})
            await _credit(db, fd["user_id"], fd["amount"])
            return {"amount": fd["amount"], "interest": 0, "held": interest}
        return None
    if await _close(db, fd, status, interest, now):
        await _credit(db, fd["user_id"], fd["amount"] + interest)
        return {"amount": fd["amount"], "interest": interest, "held": 0}
    return None


async def settle(db, user_id, now=None):
    now = time.time() if now is None else now
    quiet_player = await player_quiet(db, user_id, now)
    paid = []

    for fd in await _list(db, user_id, "active"):
        end = min(now, fd["matures_at"])
        if end > fd["last_settled_at"]:
            days = await active_seconds(db, fd["last_settled_at"], end) / DAY
            accrued = fd["accrued"] + fd["period_interest"] * fd["multiplier"] * days / RATE_PERIOD_DAYS
            res = await db.stock_fixed_deposits.update_one(
                {"_id": fd["_id"], "last_settled_at": fd["last_settled_at"]},
                {"$set": {"accrued": accrued, "last_settled_at": end}},
            )
            if res.modified_count != 1:
                continue
            fd["accrued"] = accrued
        if now >= fd["matures_at"]:
            result = await _pay_out(db, fd, int(fd["accrued"]), "matured", quiet_player, now)
            if result:
                paid.append(result)

    if not quiet_player:
        for fd in await _list(db, user_id, "held"):
            released = int(fd["interest"] * (1 - HELD_PENALTY))
            res = await db.stock_fixed_deposits.update_one(
                {"_id": fd["_id"], "status": "held"},
                {"$set": {"status": "released", "released_interest": released, "released_at": now}},
            )
            if res.modified_count == 1:
                await _credit(db, user_id, released)
                paid.append({"amount": 0, "interest": released, "held": 0})

    return paid


async def open_fd(db, user_id, amount, days, now=None):
    now = time.time() if now is None else now
    if days not in TENURES:
        raise LimitError(f"Tenure must be one of: {', '.join(str(d) for d in TENURES)} days.")
    if amount < MIN_FD_AMOUNT:
        raise LimitError(f"Minimum deposit is ₹{MIN_FD_AMOUNT / 100:,.2f}.")

    paid = await settle(db, user_id, now)
    active = await _list(db, user_id, "active")
    if len(active) >= MAX_FDS_PER_PLAYER:
        raise LimitError(f"You can have at most {MAX_FDS_PER_PLAYER} active fixed deposits.")

    median = await median_balance(db) or amount
    cap = MAX_TOTAL_IN_MEDIANS * median
    if sum(fd["amount"] for fd in active) + amount > cap:
        raise LimitError(f"Total fixed deposits can't exceed ₹{cap / 100:,.2f}.")

    res = await db.stock_balances.update_one(
        {"user_id": int(user_id), "balance": {"$gte": int(amount)}},
        {"$inc": {"balance": -int(amount)}},
    )
    if res.modified_count != 1:
        raise InsufficientFundsError("Insufficient funds for this deposit.")

    fd = {
        "user_id": int(user_id), "amount": int(amount), "days": int(days),
        "multiplier": TENURES[days], "median": median,
        "period_interest": slab_interest(amount, median),
        "opened_at": now, "matures_at": now + days * DAY, "last_settled_at": now,
        "accrued": 0.0, "status": "active",
    }
    fd["_id"] = (await db.stock_fixed_deposits.insert_one(dict(fd))).inserted_id
    return fd, paid


async def break_fd(db, user_id, number, now=None):
    now = time.time() if now is None else now
    paid = await settle(db, user_id, now)
    active = await _list(db, user_id, "active")
    if not 1 <= number <= len(active):
        raise NotFoundError("No active fixed deposit with that number.")

    fd = active[number - 1]
    held_days = (now - fd["opened_at"]) / DAY
    earned_mult = max(0.0, tenure_multiplier(held_days) - EARLY_BREAK_PENALTY)
    interest = int(fd["accrued"] * min(1.0, earned_mult / fd["multiplier"]))
    result = await _pay_out(db, fd, interest, "broken", await player_quiet(db, user_id, now), now)
    if result is None:
        raise NotFoundError("That fixed deposit was already closed.")
    result["forfeited"] = int(fd["accrued"]) - interest
    return result, paid


async def list_fds(db, user_id, now=None):
    paid = await settle(db, user_id, now)
    return await _list(db, user_id, "active"), await _list(db, user_id, "held"), paid


async def settle_all(db, now=None):
    users = await db.stock_fixed_deposits.distinct("user_id", {"status": {"$in": ["active", "held"]}})
    for user_id in users:
        await settle(db, user_id, now)
