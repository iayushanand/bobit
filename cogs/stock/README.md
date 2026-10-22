# Discord Stock Market System

> **Purpose:** A simulated, server-native stock market where Discord
> members can create publicly traded stocks, trade shares with virtual
> currency, and influence prices through chat activity and trading. This
> is a game economy, not a real-money investment product.

## Instructions for the coding LLM

Implement this feature incrementally. **Keep all stock-system code
inside `cogs/stock/`**, except for the smallest necessary integration
changes to the existing bot (such as registering the cog or reusing the
bot's existing economy/database services).

Before changing code:

1.  Inspect the repository and identify the Discord library, Python
    version, database layer, command style, cog loader, currency/economy
    system, and test setup.
2.  Reuse existing project conventions and services. Do not create a
    second currency system or database connection if the project already
    has one.
3.  Present a short implementation plan and identify any assumptions
    that need confirmation.
4.  Implement only the current phase, run its tests, report changed
    files and results, and wait before moving to the next phase unless
    explicitly instructed to continue.
5.  Do not silently rewrite unrelated bot code. Keep integration changes
    minimal and backwards-compatible.
6.  Never use real money, real brokerage APIs, or actual financial
    accounts. All balances and prices are simulated game data.

------------------------------------------------------------------------

## 1. Product overview

Members can create a stock associated with their Discord identity. Other
members can buy and sell shares. The price changes gradually based on
activity, but it should not simply mirror message counts.

The market has three main influences:

1. **Stock-owner activity:** A small, bounded signal based only on qualifying Discord activity from the stock's owner. This is the stronger of the two activity signals.
2. **Stock-holder activity:** A smaller, bounded signal based only on qualifying Discord activity from members who currently hold at least one share of that stock. This signal must have less influence than the owner's activity.
3. **Trading pressure:** Actual buy and sell orders have the strongest short-term effect. Buying creates upward pressure; selling creates downward pressure. Price impact depends on trade size relative to liquidity, not just the number of commands.

Do not use overall server chat activity as a stock-price input. A message affects a stock's activity score only when its author is that stock's owner or a current holder. If a member owns or holds multiple stocks, their qualifying activity may contribute to each applicable stock, subject to per-stock caps and anti-spam controls.

The market should also have a gradual baseline drift/noise component so
prices do not freeze when chat is quiet. Inactivity should generally
cause a stock to lose some value over time, but the fall must be
gradual, bounded, and configurable. Avoid guaranteed exponential
collapse.

### Design principles

-   **Fairness:** Prevent spam, self-trading exploits, wash trading, and
    price manipulation.
-   **Predictability:** Explain price movements in a `/stock chart` or
    `/stock info` view with a breakdown of contributing factors.
-   **Bounded movement:** Every update has a maximum percentage move. A
    single message or trade must not send a stock to zero or infinity.
-   **Atomic trades:** Cash, shares, orders, and price impact must
    update together in one database transaction.
-   **Auditability:** Record trades and price events so users can
    inspect history and admins can investigate abuse.
-   **Configurable tuning:** Keep economic parameters in one
    configuration module or settings table, not scattered through
    commands.
-   **Testability:** Price calculations should be pure functions where
    possible, separate from Discord command handlers.
-   **No fake precision:** Display sensible decimal places and document
    that prices are simulated.

## 2. Suggested gameplay and additional features

Implement the core market first. Consider these optional features after
it is stable.

### Core features

-   Create a stock with a unique ticker and display name.
-   One stock per member by default; make this configurable if multiple
    stocks are desired.
-   Starting price and initial share supply.
-   Buy and sell shares with virtual currency.
-   Portfolio, cash balance, stock info, market overview, and
    leaderboard commands.
-   Price history and a simple chart or ASCII sparkline.
-   Transaction history and recent market events.
-   Daily or periodic market summaries.
-   Cooldowns and rate limits for commands and activity scoring.
-   Admin controls to pause trading, delist a stock, adjust
    configuration, or investigate abuse.

### Economy and market depth

-   **Liquidity / market depth:** Price impact depends on trade value
    relative to liquidity. Large trades have larger impact than small
    trades.
-   **Transaction fee:** A configurable small fee can act as a currency
    sink and reduce spam trading.
-   **Spread:** Optional bid/ask spread to make immediate trading less
    exploitable.
-   **Limit orders:** Buy or sell only when the price reaches a chosen
    threshold. This is an advanced feature and should be implemented
    after basic market orders.
-   **Dividends:** Periodic payouts to holders from a configurable game
    pool. Avoid creating unlimited currency.
-   **IPO / initial offering:** A stock creator receives an initial
    allocation or sells a defined supply to the market.
-   **Share supply rules:** Fixed supply initially; consider splits or
    new issuance only later.
-   **Delisting:** Admins can freeze a stock with a documented
    settlement policy.
-   **Market events:** Random, bounded events such as a small positive
    or negative sentiment shock. Events must not override the core
    activity/trading rules.
-   **Sector tags:** Let stocks be categorized for browsing and themed
    leaderboards.
-   **Achievements:** Rewards for first trade, holding through a period,
    or using limit orders. Do not reward message spam.
-   **Watchlist:** Follow stocks and receive opt-in alerts for large
    price changes.
-   **Price alerts:** Notify a member when a stock crosses a threshold.
-   **Company profile:** Creator-provided description, category, and
    icon, with length limits and moderation.
-   **Trading halt:** Temporarily halt trading after extreme volatility
    or during admin intervention.
-   **Seasonal resets:** Optional market seasons with clear advance
    notice and exportable history.
-   **Market health panel:** Show volatility, total market
    capitalization, active traders, and liquidity.
-   **Server-wide news feed:** Post meaningful market events to a
    dedicated channel, with configurable frequency to avoid spam.

### Features to defer

Do not implement these in the initial release:

-   Derivatives, options, leverage, margin, short selling, or borrowing
    shares.
-   Complex order books and matching engines.
-   Player-created market makers.
-   Cross-server trading or shared economies.
-   Real money, crypto, external exchanges, or anything presented as
    real investment advice.

These features substantially increase complexity and create avoidable
exploit surfaces.

------------------------------------------------------------------------

## 3. Price model

Use a transparent, bounded model with separate signals for chat, owner
activity, trading, and baseline drift.

### 3.1 Price state

Each stock should store at least:

-   `stock_id`
-   `owner_user_id`
-   `guild_id`
-   `ticker`
-   `name`
-   `description` (optional)
-   `current_price`
-   `initial_price`
-   `total_shares`
-   `available_shares` or another explicit supply representation
-   `liquidity`
-   `created_at`
-   `last_price_update_at`
-   `last_owner_activity_at`
-   `status` (`active`, `halted`, `delisted`)
-   Optional rolling activity/sentiment metrics

Use a consistent currency representation. Prefer integer minor units
(for example, cents) or `Decimal` for money values. Do not use binary
floating-point for balances or trade settlement. If using floats for a
simulation calculation, convert and quantize carefully at the boundary.

### 3.2 Owner and holder activity scoring

Do not use overall server message volume. For each stock, score only qualifying messages from the stock owner and members who currently hold at least one share of that stock.

A member who neither owns nor holds a stock must not affect that stock's activity score. Determine holder eligibility from current holdings when activity is processed, and document how activity is handled if a member sells their final share.

Recommended scoring rules:

- Ignore bots, webhooks, empty messages, command-only messages, and messages that fail basic anti-spam checks.
- Apply a per-user scoring cooldown, initially around 30–60 seconds, and per-stock/per-window caps.
- Use a rolling window or time-decaying score so old activity gradually loses influence.
- Do not reward message length alone.
- Allow configured channels to be excluded from activity scoring.
- Do not score multiple edits to the same message as new activity.
- Do not store message bodies. Store only the minimal timestamps/identifiers or aggregate counters needed for scoring.

Normalize owner and holder activity separately to the range `0` to `1`, with diminishing returns. For example:

`owner_score = min(1, qualifying_owner_activity / owner_activity_target)`

`holder_score = min(1, qualifying_holder_activity / holder_activity_target)`

The implementation may use `log1p` or another saturating function, but it must be deterministic and testable. Use distinct configurable weights with **owner weight greater than holder weight**. A reasonable starting relationship is an owner activity weight about 2–3 times the holder activity weight, while keeping both small relative to trade impact. Treat this as a tuning target, then validate it through simulations.

Aggregate holder activity without letting one holder or a large number of holders create unlimited price growth. Normalize and cap the aggregate, and apply diminishing returns per member. Do not simply add every holder's raw message count together.

Recent qualifying activity can create a small positive contribution. As activity becomes stale, its contribution should fade gradually. Prolonged inactivity should contribute to gradual negative decay, but the stock must not crash immediately when its owner or holders go offline.

If the owner also holds shares, count their messages only in the owner signal, not again in the holder aggregate. A message can contribute at most once to a stock's activity calculation per scoring window.

### 3.3 Owner activity signal

The owner's activity should have a small, bounded effect. It must be stronger than the holder-activity signal, but both activity signals must remain much weaker than trade impact.

- Recent qualifying owner activity provides a tiny positive or neutral modifier.
- As owner activity becomes stale, the positive contribution fades and may become a small negative modifier.
- Cap the owner contribution per scheduled update.
- Use a time horizon of hours or days, not a price change for every message.
- Do not make the stock crash immediately if the owner goes offline.
- Prevent owners from pumping their stock through message spam using cooldowns, caps, and diminishing returns.

Calculate the owner signal from qualifying owner activity, not merely from command usage.

### 3.3.1 Holder activity signal

The holder signal is based only on qualifying activity from members who currently own at least one share of the stock, excluding the stock owner to prevent double-counting. Its weight must be lower than the owner signal. Aggregate it with per-member diminishing returns and a stock-level cap so a large holder count cannot create unlimited upward pressure.

Document the eligibility policy for members who sell all their shares. By default, their future messages stop contributing immediately; historical activity already accumulated in the current window may decay naturally rather than being abruptly erased.

### 3.4 Trading pressure and liquidity

Trading must have the strongest direct short-term price impact.

For each completed trade, calculate signed pressure from trade value
relative to liquidity:

-   Buy: positive pressure.
-   Sell: negative pressure.
-   Larger trades relative to liquidity: larger pressure.
-   Small trades: small price movement.
-   Apply configurable caps so one trade cannot cause an unlimited move.

A possible conceptual formula is:

`trade_impact = sensitivity * signed_trade_value / max(liquidity, minimum_liquidity)`

Then clamp the result to a configured maximum absolute percentage
change. This is a starting model, not a mandate to use this exact
formula. Test it against small, medium, and large trades.

Important design choice: **do not count the same trade twice.** If trade
execution directly changes the price, do not also add the same trade to
a periodic trade-pressure accumulator unless the second effect is
intentional and documented.

For the initial implementation, market orders are enough. Price the
order from a consistent pre-trade price, calculate the fee and impact,
validate funds/shares, then commit the trade, balance/share changes, and
price event atomically.

### 3.5 Inactivity decay and baseline drift

The stock should slowly fall when it has no qualifying activity, but not
collapse just because a scheduled task runs many times.

Recommended behavior:

-   Calculate elapsed time since the previous price update.
-   Use a time-based decay formula rather than applying the same fall
    every time a task executes.
-   Set a small maximum decay rate per hour or day.
-   Use a price floor greater than zero.
-   Do not use repeated compounding at an uncontrolled interval.
-   Consider a tiny bounded random drift for realism, but make it
    deterministic in tests by injecting the random generator or seed.
-   Avoid making all stocks fall at exactly the same rate unless that is
    an intentional server-wide mechanic.

An exponential form such as `decay = exp(-rate * elapsed_time)` can make
results independent of how often the updater runs, but the rate must be
small and the final change must still respect the movement cap. A linear
or piecewise model is also acceptable if its behavior is documented.

### 3.6 Combine the signals

Use a log-return or percentage-change model so prices remain positive
before applying the floor:

`raw_return = owner_activity_component + holder_activity_component + inactivity_component + trade_component + baseline_component`

Then:

1.  Clamp `raw_return` to a configurable maximum positive and negative
    move per update.
2.  Apply it to the prior price.
3.  Enforce the minimum price and configured maximum price.
4.  Quantize the displayed/settled price to the currency precision.
5.  Persist the new price and a breakdown of the event.

For a periodic update, trade impact should normally be zero if trades already change price immediately. Owner and holder signals should be small, with the owner's influence higher than the holder aggregate. Inactivity decay should be gradual. Provisional initial tuning targets per scheduled interval at maximum normalized signal:

- Owner activity: around `±0.05%` to `±0.10%`.
- Holder activity: around `±0.02%` to `±0.04%`, and always less influential than the owner signal.
- Trade impact: may exceed either activity contribution and should scale with trade size relative to liquidity, while remaining capped.
- Inactivity decay: gradual and configurable, measured over hours or days rather than per message.

These are provisional ranges, not fixed economic rules. Define the interval and units precisely, then validate them using multi-day simulations. Messages from people who neither own nor hold the stock have no direct price effect.

### 3.7 Price update cadence

-   Never update prices directly on every Discord message.
-   Record eligible activity cheaply and aggregate it.
-   Use a scheduled task (for example, every 5--15 minutes) for
    activity-based changes.
-   Apply trade pressure immediately at trade execution, or use an
    explicitly designed batch model, not both by accident.
-   Persist `last_price_update_at` and calculate elapsed time after
    downtime.
-   On restart, process elapsed time safely without applying the same
    time interval twice.
-   Add a single-instance/lease guard if multiple bot processes could
    run the updater.

------------------------------------------------------------------------

## 4. Trading and ownership rules

Define these rules before implementing commands.

### Stock creation

-   A member can create at most one stock per guild in the first
    version.
-   Tickers are normalized to uppercase and unique within a guild.
-   Validate ticker length and allowed characters, for example 2--8
    letters/numbers.
-   Stock creation has a configurable fee or minimum account balance if
    the existing economy supports it.
-   Set initial price, initial share supply, and creator allocation
    explicitly.
-   Do not grant unlimited shares or money through repeated creation
    attempts.
-   Apply a cooldown and log administrative actions.

### Buying

-   Validate stock status, requested quantity, available shares,
    balance, fees, and price bounds.
-   Prevent negative or zero quantities.
-   Calculate total cost from the actual execution price and configured
    fee.
-   Use a database transaction with appropriate row locking or
    concurrency protection.
-   Update buyer balance, share holdings, stock supply/liquidity as
    designed, trade record, and price event atomically.
-   Return a clear receipt showing quantity, execution price, gross
    amount, fee, and total charged.

### Selling

-   Validate stock status, requested quantity, owned shares, fees, and
    price bounds.
-   Do not allow a user to sell more shares than they own.
-   Use an atomic transaction.
-   Return a receipt showing quantity, execution price, gross proceeds,
    fee, and net proceeds.
-   A sale should create negative price pressure, scaled by liquidity
    and trade size.

### Ownership and supply model

Pick one coherent supply model and document it. Recommended for version
1:

-   Each stock has a fixed total share supply.
-   The creator receives a configured initial allocation.
-   A defined number of shares are available for purchase from the
    initial offering.
-   Shares move between members when they trade.
-   If the implementation instead allows the system to buy shares back
    or mint new shares, document that explicitly and test the accounting
    invariants.

Do not accidentally treat the stock's total supply, the issuer's
holdings, and the market's available shares as the same number.

### Portfolio accounting

-   Keep cash balances and share holdings separate.
-   A member can own shares of multiple stocks.
-   Use a unique constraint on `(guild_id, user_id, stock_id)` for
    holdings, or an equivalent structure.
-   Portfolio market value is a display estimate based on the current
    price. It is not guaranteed sale proceeds because fees, liquidity,
    and price impact can change execution results.
-   Track realized profit/loss and average cost only if the accounting
    method is explicitly chosen. FIFO or weighted-average cost are
    reasonable options; do not mix methods.
-   If the existing bot already has an economy system, integrate with it
    instead of maintaining conflicting balances.

------------------------------------------------------------------------

## 5. Suggested Discord commands

Match the existing bot's command framework and naming conventions. These
are proposed user-facing commands, not a requirement to use a specific
slash-command implementation.

  -----------------------------------------------------------------------
  Command                             Purpose
  ----------------------------------- -----------------------------------
  `.stock create ticker name`         Create a stock

  `.stock info ticker`                Show price, owner, activity,
                                      supply, liquidity, and status

  `.stock market`                     Browse active stocks and recent
                                      movers

  `.stock buy ticker quantity`        Buy shares

  `.stock sell ticker quantity`       Sell shares

  `.stock portfolio [member]`         Show holdings and estimated value

  `.stock balance [member]`           Show virtual cash balance, or defer
                                      to the existing economy command

  `.stock history ticker`             Show recent price changes and
                                      trades

  `.stock chart ticker period`        Show a chart or sparkline over a
                                      supported period

  `.stock trades [member]`            Show recent trade history

  `.stock leaderboard metric`         Rank members by portfolio value,
                                      realized profit, or trading
                                      activity

  `.stock watch ticker`               Add a stock to the user's watchlist

  `.stock unwatch ticker`             Remove a stock from the watchlist

  `.stock alert ticker price`         Add a price alert

  `.stock help`                       Explain rules and calculations
  -----------------------------------------------------------------------

Admin-only commands may include `.stock admin pause`,
`.stock admin resume`, `.stock admin halt`, `.stock admin delist`,
`.stock admin config`, and `.stock admin audit`. Use the project's
existing permission checks and ensure that ordinary members cannot
invoke admin actions.

Keep initial scope small: create, info, market, buy, sell, portfolio,
and history are sufficient for the first playable release.

------------------------------------------------------------------------

## 6. Database and persistence

First inspect the current database and migration approach. Use the
existing database if appropriate. Do not assume SQLite, PostgreSQL,
MongoDB, or a specific ORM without checking the repository.

A relational schema is a natural fit because trade settlement updates
several related records atomically. If the bot already uses another
database, use its established conventions and implement equivalent
constraints/transactions where possible.

Suggested logical tables:

### `stocks`

Stores stock identity, ownership, price, supply, liquidity, status, and
timestamps.

### `stock_holdings`

Stores the quantity of each stock held by each member.

Suggested unique key: `(guild_id, user_id, stock_id)`.

### `stock_trades`

Immutable trade ledger with buyer/seller or actor, stock, side,
quantity, execution price, gross value, fee, net value, and timestamp.

### `stock_price_history`

Stores timestamped prices and the reason for a price update. Include
components such as owner activity, holder activity, inactivity, trade, and baseline
where useful.

### `stock_activity`

Stores aggregated activity windows or counters, not necessarily every
message. Prefer compact aggregates to avoid unbounded row growth.

### `stock_watchlists` and `stock_alerts`

Optional tables for opt-in notifications.

### `stock_config` or application configuration

Stores tunable market parameters, or keep these in a validated
configuration file if that matches the project.

### Accounting invariants

Add tests and, where supported, database constraints for these
conditions:

-   Cash balances cannot become negative unless the existing economy
    explicitly permits debt.
-   Holdings cannot become negative.
-   A trade's debits and credits reconcile, including fees.
-   Fixed share supply is conserved unless a documented issuance/buyback
    event occurs.
-   Each trade is applied exactly once.
-   Stock ticker uniqueness is enforced by the database, not just an
    application-side check.
-   A failed transaction leaves balances, holdings, trades, and price
    unchanged.
-   Repeated event processing cannot apply the same price interval
    twice.

Use migrations rather than silently recreating tables. Preserve existing
user balances and data.

------------------------------------------------------------------------

## 7. Suggested folder structure

Create the stock system under `cogs/stock/`. Adapt filenames to existing
project conventions, but keep clear separation between Discord commands,
domain logic, persistence, and scheduled jobs.

``` text
cogs/
└── stock/
    ├── __init__.py
    ├── cog.py                 # Discord command group and listeners
    ├── service.py             # Use cases: create, buy, sell, portfolio
    ├── pricing.py             # Pure price/activity formulas
    ├── models.py              # Domain models / typed structures
    ├── repository.py          # Database reads and writes
    ├── market_tasks.py        # Scheduled price updates and maintenance
    ├── activity.py            # Owner/holder eligibility, filtering, and aggregation
    ├── validators.py          # Ticker, quantity, and input validation
    ├── config.py              # Defaults and validated configuration
    ├── charts.py              # Matplotlib chart rendering to PNG/BytesIO
    ├── statistics.py          # Historical statistics and chart datasets
    ├── exceptions.py          # Domain-specific errors
    └── tests/
        ├── test_pricing.py
        ├── test_trading.py
        ├── test_activity.py
        ├── test_accounting.py
        └── test_charts.py
```

If the project has shared database models, migrations, or test folders,
follow those conventions while keeping stock-specific implementation
inside `cogs/stock/`. Do not force this exact layout if the repository
has an established architecture.

------------------------------------------------------------------------


## 7.1. Statistics and chart rendering with Matplotlib

Use **Matplotlib** to render stock statistics as image attachments that Discord can display. Charts should be generated from persisted stock price history and trade records, not from fabricated or randomly generated data.

### Architecture and dependency

- Keep all stock-specific chart code in `cogs/stock/charts.py`; keep aggregation/query logic in `cogs/stock/statistics.py` or the existing service/repository layer.
- During Phase 0, inspect the project's Python version and dependency management (`requirements.txt`, `pyproject.toml`, Poetry, uv, etc.) and verify that a compatible Matplotlib version can be installed.
- Add Matplotlib to the project's existing dependency file only when implementing the chart phase. Do not create a second dependency-management system.
- Use a non-interactive backend such as `Agg`, set before importing `matplotlib.pyplot`, because the bot runs headlessly on a server.
- Render images in memory using `io.BytesIO` and send them through the Discord library's file attachment API. Do not write a permanent PNG to disk for every command.
- Close figures after rendering to avoid memory leaks. Ensure chart generation does not block the event loop for too long; if rendering becomes expensive, offload it to a worker thread or executor.
- Keep database access out of the plotting functions. Pass validated, ordered data into chart-rendering functions so they can be unit-tested independently.
- Apply sensible limits to the requested date range and number of points. Downsample long histories when needed, while preserving important price changes.
- Use readable titles, axis labels, dates, legends, and currency formatting. Handle empty history and a single data point gracefully.
- Never use a chart to imply a guaranteed future price. Historical charts describe past simulated data only.

### Recommended charts

1. **Price history line chart:** Price over a selected period such as 1 hour, 24 hours, 7 days, or 30 days.
2. **Volume chart:** Number of shares and/or virtual currency traded over time.
3. **Daily percentage change:** Daily returns, clearly labelled as simulated-market changes.
4. **Portfolio allocation chart:** Distribution of a member's estimated portfolio value by ticker. Limit the number of slices and group small holdings into “Other”.
5. **Market overview:** Top gainers and losers over a chosen period.
6. **Activity versus price chart:** Plot aggregated owner and holder activity separately from price on separate axes or in separate aligned panels. Clearly label the scales and do not imply correlation proves causation.
7. **Price movement breakdown:** Show how owner activity, holder activity, inactivity decay, trade pressure, and baseline movement contributed to a price update, if those components are persisted.

### Suggested command interface

- `/stock chart ticker period`: Attach a price history graph for a supported period.
- `/stock stats ticker period`: Show current price, absolute and percentage change, high/low, volatility, trade volume, and data coverage, with a chart where useful.
- `/stock portfolio [member]`: Optionally attach a portfolio allocation chart when the member holds multiple stocks.
- `/stock market`: Optionally display a compact top-gainers/losers chart or attach a separate chart command rather than making every response image-heavy.

Keep chart commands responsive and limit how frequently a user can request expensive renders. If chart rendering fails, return a useful text response and log the exception without crashing the cog.

### Chart implementation checklist

- Use timezone-aware timestamps consistently and convert them to a readable display timezone.
- Sort historical records by timestamp before plotting.
- Label prices in the bot's virtual currency and include the requested period in the title.
- Do not connect points across missing-data gaps as if observations existed.
- Avoid plotting one line per user in a large server; aggregate activity to protect privacy and readability.
- Use a deterministic plotting style and test the generated image's existence, format, and non-zero size without relying on exact pixel comparisons.
- Avoid setting explicit colors unless the project has an established chart theme; make charts legible in both light and dark Discord clients where possible.
- If Matplotlib is unavailable or cannot be imported, disable chart commands cleanly and explain the missing dependency in logs.

## 8. Security, abuse prevention, and reliability

-   Ignore bots, webhooks, and command-only messages for activity
    scoring unless explicitly configured.
-   Use cooldowns and per-user scoring caps.
-   Do not score multiple edits to the same message as new activity.
-   Do not score deleted messages as new activity; optionally reverse
    activity if deletion is a moderation signal, but avoid complex
    reversal logic in version 1.
-   Prevent self-trading if the model supports direct counterparties.
-   Detect repeated buy/sell cycles and suspicious volume where
    practical.
-   Ensure users cannot manipulate price by splitting one large trade
    into many small trades if fees and impact rules make that
    profitable. Consider aggregating pressure over a short window or
    using a concave impact function.
-   Use parameterized database queries.
-   Validate all command inputs server-side.
-   Use authorization checks for owner and admin actions.
-   Use database transactions and concurrency controls for simultaneous
    commands.
-   Avoid doing slow database operations directly inside high-frequency
    message listeners. Queue or aggregate updates as appropriate.
-   Add structured logs for trades, price updates, rejected trades, and
    admin actions. Do not log secrets or unnecessary message content.
-   Make background tasks cancel cleanly when the cog unloads and avoid
    starting duplicate loops on reload.
-   Handle Discord API errors and database outages without losing
    accounting consistency.
-   Provide a pause switch for trading and scheduled price updates.
-   Include a clear disclaimer that this is a simulated game market.

------------------------------------------------------------------------

## 9. Testing and simulation

Pricing is an economic system, so tests must cover both code correctness
and behavior over simulated time.

### Unit tests

Test pure functions with fixed inputs:

-   No activity produces the expected small decay.
-   Increasing eligible activity raises the activity signal but
    saturates at the cap.
-   Owner activity has much smaller impact than chat activity.
-   Owner inactivity does not create a sudden crash.
-   A small buy has a small positive impact.
-   A larger buy relative to liquidity has greater positive impact.
-   A sell has negative impact.
-   Price changes respect per-update caps.
-   Price never falls below the configured floor or exceeds the ceiling.
-   Elapsed-time calculations are independent of task invocation
    frequency within expected tolerance.
-   Invalid or negative quantities are rejected.
-   Rounding and fees are correct.

### Integration tests

-   Create a stock and verify database state.
-   Buy and sell shares and verify balances, holdings, trade ledger, and
    price history.
-   Two simultaneous buys cannot overspend the same balance or sell the
    same shares twice.
-   A failed trade rolls back all related writes.
-   Repeated cog reloads do not create duplicate background tasks.
-   A bot restart does not double-apply inactivity decay.
-   Activity from bots, excluded channels, spam, and commands is ignored
    according to configuration.

### Simulation tests

Build a deterministic simulator that can run multiple virtual days with
configurable activity and trades. It should cover at least these
scenarios:

1.  Quiet stock with no owner activity.
2.  Active owner but quiet server.
3.  Active owner and holders with small trades.
4.  Busy server chat from people who neither own nor hold the stock; their activity must have no direct effect.
5.  Large buy relative to liquidity.
6.  Large sell relative to liquidity.
7.  One user attempting to spam messages.
8.  Alternating buy/sell trades attempting to exploit the price formula.
9.  Bot downtime followed by restart.
10. Many stocks with different activity levels.

Report price change over time, volatility, maximum drawdown, and whether
the configured caps were respected. Do not tune the model using only
one-day examples.

### Acceptance criteria

-   No single chat message directly causes a noticeable price jump.
-   Owner activity has a visibly smaller effect than normal stock
    activity.
-   A large trade affects price more than a small trade, in the correct
    direction.
-   A sell causes downward pressure; a buy causes upward pressure.
-   Inactivity leads to gradual decay over a long enough period, not an
    immediate collapse.
-   No price can become zero, negative, infinite, or NaN.
-   Concurrent trades cannot create money or shares.
-   Every completed trade has a corresponding immutable ledger entry.
-   Price history explains why a price changed.
-   Matplotlib chart commands can render historical price graphs and statistics as Discord image attachments.
-   Chart generation handles missing data and runs safely in a headless bot environment.
-   The feature can be disabled or paused without corrupting data.

------------------------------------------------------------------------

## 10. Implementation phases

Complete and test each phase before proceeding. Do not implement all
phases in one large change.

### Phase 0: Repository reconnaissance and plan

**Goal:** Understand the existing bot before writing code.

Tasks: - Identify Python version and Discord library. - Inspect cog
loading and command registration. - Identify database, migrations, and
economy services. - Identify how guild-specific settings and permissions
are handled. - Identify the test framework and lint/type-check
commands. - Propose the smallest compatible integration plan.

Deliverable: a short plan, proposed files, risks, and any questions. No
implementation changes yet.

**Test/check:** Confirm the current project can start and existing tests
pass, or record baseline failures.

### Phase 1: Domain models, configuration, and pricing functions

**Goal:** Build a deterministic core without Discord commands or
database side effects.

Tasks: - Add stock/domain structures and validated configuration. -
Implement normalized activity scoring. - Implement owner activity signal
with very small weight. - Implement time-based inactivity decay. -
Implement bounded trade impact based on trade value and liquidity. -
Implement price combination, clamping, and quantization. - Document
units and default tuning values.

Deliverable: `pricing.py`, `models.py`, `config.py`, and unit tests,
adjusted to repository conventions.

**Test/check:** All price formula tests pass. Demonstrate a table of
expected results for quiet, active, owner-inactive, small-buy, and
large-sell cases.

### Phase 2: Persistence and schema

**Goal:** Persist stock, holdings, trade ledger, and price history
safely.

Tasks: - Add schema/migrations using the existing database approach. -
Add repository methods and database constraints. - Implement transaction
boundaries for related writes. - Add repository tests for stock
creation, holdings, and trade history. - Ensure ticker uniqueness and
nonnegative balance/holding rules.

Deliverable: migrations/schema changes and repository implementation.

**Test/check:** Integration tests pass, including rollback behavior.
Existing bot data remains intact.

### Phase 3: Basic commands and stock creation

**Goal:** Let members create and inspect stocks.

Implement: - `/stock create` - `/stock info` - `/stock market` -
`/stock history`

Tasks: - Add validation, cooldowns, helpful error messages, and
permission checks. - Ensure stock creation cannot duplicate a ticker or
bypass the one-stock-per-member rule. - Display price, owner, supply,
liquidity, activity summary, and status.

**Test/check:** Test valid creation, duplicate ticker, invalid ticker,
repeated creation, unauthorized actions, and empty market.

### Phase 4: Buy, sell, and portfolio accounting

**Goal:** Make trading safe and playable.

Implement: - `/stock buy` - `/stock sell` - `/stock portfolio` -
Optional `/stock trades`

Tasks: - Use atomic transactions for balances, holdings, trade ledger,
and price impact. - Apply fees if enabled. - Enforce supply and
ownership rules. - Show clear trade receipts. - Calculate portfolio
value as an estimate, not guaranteed liquidation value.

**Test/check:** Verify buys, sells, fees, insufficient funds,
insufficient shares, simultaneous trades, rollback, and supply
conservation.

### Phase 5: Activity tracking and scheduled pricing

**Goal:** Connect chat activity to small, controlled price movements.

Tasks:
- Add an efficient listener/aggregation method.
- Ignore bots, commands, excluded channels, and spam according to config.
- Score activity only for the stock owner or current holders; do not use overall server activity.
- Maintain separate owner and holder aggregates, with the owner weight greater than the holder weight.
- Do not double-count owners who also hold shares.
- Add per-user cooldowns and per-window caps.
- Add the scheduled market update loop.
- Persist update timestamps and event breakdowns.
- Ensure trade impact is not counted twice.

**Test/check:** Simulate owners, holders, and unrelated members. Confirm only owners and current holders affect a stock, owner influence exceeds holder influence, both are small relative to trading, and inactivity decay is gradual. Verify reload and restart behavior.

### Phase 6: Leaderboards, charts, alerts, and market events

**Goal:** Improve engagement after the core market is stable.

Implement selectively: - Leaderboards - Price charts/sparklines -
Watchlists and opt-in alerts - Daily market summary - Bounded market
events - Optional dividends or transaction fees if not already present

**Test/check:** Notification rate limits, timezone handling,
missing-data cases, and event caps.

### Phase 7: Abuse testing, tuning, and release

**Goal:** Validate the economy over simulated time and prepare for
deployment.

Tasks: - Run deterministic multi-day simulations. - Test spam,
wash-trading, trade splitting, concurrent commands, downtime, and
database failures. - Tune price sensitivity, liquidity, decay, fees, and
caps. - Add admin pause/halt/audit controls. - Document commands,
configuration, migration, and rollback procedures. - Confirm logging
does not capture unnecessary private message content.

**Test/check:** All acceptance criteria in Section 9 are met. Provide a
concise release report and list any known limitations.

------------------------------------------------------------------------

## 11. Configuration defaults to start with

Treat these as provisional starting values. Put them in one place,
validate them at startup, and make them easy to tune.

  ------------------------------------------------------------------------
  Setting                   Suggested starting point Notes
  --------------------- ---------------------------- ---------------------
  Price update interval                   10 minutes Never update price
                                                     for every message

  Activity window        1 hour plus 24-hour context Use decay/rolling
                                                     aggregation

  Per-user                                45 seconds Prevent spam farming
  scored-message                                     
  cooldown                                           

  Owner activity contribution                    Small, capped Target roughly
                                                     0.1--0.5% per
                                                     scheduled interval at
                                                     maximum normalized
                                                     activity

  Holder activity contribution       Smaller, capped Target roughly
                                                     0.02--0.04% per
                                                     scheduled interval at
                                                     maximum signal; owner
                                                     weight must be higher

  Inactivity decay              Configurable per day Test long-run
                                                     behavior; avoid
                                                     abrupt collapse

  Maximum scheduled            Configurable, e.g. 1% Applies to periodic
  price move                                         updates, not
                                                     necessarily trade
                                                     impact

  Trade impact                Liquidity-relative and Must exceed activity
                                              capped influence for
                                                     meaningful trades

  Minimum price            Positive configured floor Prevent zero/negative
                                                     prices

  Maximum price                 Configurable ceiling Prevent
                                                     overflow/extreme
                                                     runaway

  Trading fee                         0--2% optional Avoid fees if the
                                                     existing economy has
                                                     a different policy

  Price alert threshold                 Configurable Rate-limit
                                                     notifications
  ------------------------------------------------------------------------

Do not interpret these values as a final economic balance. The tests and
simulator determine whether they produce the desired behavior.

------------------------------------------------------------------------

## 12. Definition of done

The core stock system is ready when:

-   The feature lives under `cogs/stock/` and follows existing project
    conventions.
-   Matplotlib charts and statistics are available through Discord commands and use persisted historical data.
-   Stock creation, info, market, buy, sell, portfolio, and history
    work.
-   Only stock-owner and current-holder activity affects activity-based pricing; general server chat has no direct effect.
-   Owner activity has a greater effect than holder activity, while both remain small relative to trading.
-   Activity scoring resists spam and does not double-count owners who also hold shares.
-   Trading impact scales with trade size relative to liquidity and is
    correctly signed.
-   Inactivity decay is time-based, gradual, bounded, and restart-safe.
-   Database transactions preserve balances and share supply under
    concurrency.
-   Every price update and completed trade is auditable.
-   Unit, integration, and simulation tests pass.
-   Configuration, commands, deployment, and known limitations are
    documented.

## Final instruction to the coding LLM

Start with **Phase 0 only**. Inspect the repository, report the actual
architecture and existing services, then propose the implementation
plan. Do not assume filenames, database technology, or command framework
before inspecting the project. After the plan is reviewed, implement one
phase at a time and test each phase before proceeding.
