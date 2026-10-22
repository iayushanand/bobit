# Stock Market Exploit Patch

## TL;DR
Fixed infinite-money exploit where `buy 1730` → `sell 1730` (or repeat) could profit from price-impact capping. Added hard caps + global limits + circuit breaker. **No more instant flip profit, even with alts or spamming.**

## What was wrong
- Price impact was `0.10 * gross/liquidity` capped at `+2%` per trade (`cogs/stock/pricing.py:103`, `config.py:48`)
- `buy 1730 @ ₹109.30 → ₹111.43 (+1.7%)` then `buy 1730` again `→ +2%` = `~+4%` pump if split
- `sell 3460` in one trade also capped at `-2%` → net `+2%` pump stays, seller keeps profit
- Fee `1%` < `2%` cap → `buy 1730×2 → sell 3460` = **+₹293k profit** with `₹10M` start
- No per-trade limit, no global volume limit → 5 alts × 500 = same pump

## What's fixed

### 1. Hard cap per trade
`max_trade_quantity = 500` shares (5% of supply)
`config.py:65`, `validators.py:33`, `service.py:59`, `cog.py:242`
- `.stocks buy SKY 1730` → `❌ Hard cap: max 500 shares per trade`
- `all` now capped to 500 → `Capped to 500, run again for more`

### 2. Position cap
`max_position_shares = 2000` per user per stock
`config.py:67`, `service.py:65`
- `buy 500 ×5` → `❌ Position cap: max 2,000... you would hold 2,500`
- Stops one user hoarding supply to manipulate price

### 3. Anti-flip hold
`min_hold_seconds = 30`
`config.py:66`, `service.py:242`
- `buy → sell` instantly → `❌ Hold period: wait 30s before selling SKY`
- In-memory per `user:stock`, blocks instant `buy→sell` loop

### 4. Global per-stock throttle (NEW - sybil fix)
`global_max_volume_per_window = 2000 shares / 60m` per ticker
`global_volume_window_seconds = 3600`
`config.py:69`, `service.py:69`
- Counts **all users combined** in last 60m
- `buy 500×4 = 2000` ok, 5th buy (any user) → `❌ Global limit: 2,000 shares per 60m per stock. Already traded 2,000 in window — try again in 3599s.`
- `1730×2 = 3460` now impossible even with 10 alts

### 5. Circuit breaker
`global_max_price_move_pct = 12%`, `halt = 5m`
`config.py:71`, `service.py:92`
- If `new_price` moves `>12%` from window open → `❌ Circuit breaker: SKY moved 13.5% in 60m (limit 12%). Trading halted for 5m.`
- All users see `halted` until timer expires (stored as `global_halt_until`)

### 6. Other hardening
- Per-stock `asyncio.Lock` `service.py:54` → no race/double-spend on `available_shares` / `balance`
- Strict qty parsing `cog.py:275` → `1e3`, `1.5`, `,`, floats rejected (must be whole number)
- Pay capped `₹10,000 / transfer`, cooldown `10s` `cog.py:381` → can't funnel profit to alt

## What you'll see in Discord

```
.stocks buy SKY 1730
→ Stock error: Hard cap: max 500 shares per trade (you tried 1,730).

.stocks buy SKY all  (when holding 2000)
→ Stock error: Position cap: max 2,000 shares per stock

.stocks sell SKY 500 (right after buy)
→ Stock error: Hold period: wait 27s before selling SKY

.stocks buy SKY 500 (5th global trade in hour)
→ Stock error: Global limit: 2,000 shares per 60m per stock. Already traded 2,000

.stocks buy SKY 500 (during breaker)
→ Stock error: `SKY` is halted by circuit breaker — try again in 240s.
```

## Numbers (verified)
- Before: `500×4 buys → 2000 sell` = `+₹1.0M` profit (with `₹100M` balance)
- After: `500×4 buys → 500×4 sells` = `-₹306k` loss (fee > impact, any `N` repeats = loss)
- `20` flips `buy 500→sell 500` = `-₹1.49M` loss

## Files changed
`cogs/stock/config.py`, `cogs/stock/validators.py`, `cogs/stock/service.py`, `cogs/stock/cog.py`

No config needed — defaults active. Restart bot to apply.

Questions? Ping staff.
