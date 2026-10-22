"""Validated tunable parameters for the simulated stock market.

All money values are integer minor units (e.g. cents/paise) to avoid
binary floating-point errors during settlement. Returns are floats
representing fractional price changes (0.01 == 1%).

Tuning targets (per scheduled interval at maximum normalized signal,
see README Sections 3.6 and 11):
- Owner activity:   up to ``owner_max_return`` (default 0.10%).
- Holder activity:  up to ``holder_max_return`` (default 0.04%),
  always less than the owner signal (~2.5x ratio).
- Trade impact:     liquidity-relative, capped by ``max_trade_move``
  (default 5%), intentionally larger than either activity signal.
- Inactivity decay: time-based exponential, ``inactivity_decay_per_day``
  (default 2%/day), gradual and restart-safe.

Note: README Section 11 suggests 0.1-0.5% for owner contribution while
Section 3.6 suggests 0.05-0.10%. This module follows Section 3.6
(0.10% owner / 0.04% holder) as the authoritative periodic-update
target; widen only after multi-day simulation validation.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StockConfig:
    """Immutable market tuning. Validate on construction."""

    price_update_interval_minutes: int = 10
    scoring_cooldown_seconds: int = 45
    activity_window_seconds: int = 3600

    owner_activity_target: int = 10
    holder_activity_target: int = 20
    holder_per_member_cap: int = 5

    owner_max_return: float = 0.001
    holder_max_return: float = 0.0004
    stale_horizon_hours: float = 48.0

    inactivity_decay_per_day: float = 0.02
    baseline_vol: float = 0.0002

    max_scheduled_move: float = 0.01
    trade_sensitivity: float = 0.10
    minimum_liquidity_minor: int = 100_000
    max_trade_move: float = 0.05

    min_price_minor: int = 100
    max_price_minor: int = 100_000_000

    trading_fee_rate: float = 0.01
    currency_precision: int = 2
    currency_symbol: str = "₹"

    starting_balance_minor: int = 1_000_000
    initial_price_minor: int = 10_000
    total_supply: int = 10_000
    creator_allocation: int = 1_000
    creation_fee_minor: int = 0
    max_stocks_per_member: int = 1

    excluded_channel_ids: tuple = field(default_factory=tuple)
    command_prefixes: tuple = field(default_factory=lambda: (".",))

    def __post_init__(self) -> None:
        if self.price_update_interval_minutes <= 0:
            raise ValueError("price_update_interval_minutes must be positive")
        if self.scoring_cooldown_seconds < 0:
            raise ValueError("scoring_cooldown_seconds cannot be negative")
        if self.activity_window_seconds <= 0:
            raise ValueError("activity_window_seconds must be positive")
        if self.owner_activity_target < 1:
            raise ValueError("owner_activity_target must be >= 1")
        if self.holder_activity_target < 1:
            raise ValueError("holder_activity_target must be >= 1")
        if self.holder_per_member_cap < 1:
            raise ValueError("holder_per_member_cap must be >= 1")
        if not 0 <= self.owner_max_return <= self.max_scheduled_move:
            raise ValueError("owner_max_return must be within [0, max_scheduled_move]")
        if not 0 <= self.holder_max_return < self.owner_max_return:
            raise ValueError("holder_max_return must satisfy 0 <= holder < owner")
        if self.stale_horizon_hours <= 0:
            raise ValueError("stale_horizon_hours must be positive")
        if self.inactivity_decay_per_day < 0:
            raise ValueError("inactivity_decay_per_day cannot be negative")
        if self.baseline_vol < 0:
            raise ValueError("baseline_vol cannot be negative")
        if self.max_scheduled_move <= 0:
            raise ValueError("max_scheduled_move must be positive")
        if self.trade_sensitivity < 0:
            raise ValueError("trade_sensitivity cannot be negative")
        if self.minimum_liquidity_minor < 1:
            raise ValueError("minimum_liquidity_minor must be >= 1")
        if self.max_trade_move <= 0:
            raise ValueError("max_trade_move must be positive")
        if not 1 <= self.min_price_minor < self.max_price_minor:
            raise ValueError("require 1 <= min_price < max_price")
        if not 0 <= self.trading_fee_rate <= 0.05:
            raise ValueError("trading_fee_rate must be within [0, 5%]")
        if self.starting_balance_minor < 0:
            raise ValueError("starting_balance_minor cannot be negative")
        if not self.min_price_minor <= self.initial_price_minor <= self.max_price_minor:
            raise ValueError("initial_price must be within [min_price, max_price]")
        if self.total_supply < 1:
            raise ValueError("total_supply must be >= 1")
        if not 0 <= self.creator_allocation < self.total_supply:
            raise ValueError("creator_allocation must satisfy 0 <= alloc < total_supply")
        if self.creation_fee_minor < 0:
            raise ValueError("creation_fee_minor cannot be negative")
        if self.max_stocks_per_member < 1:
            raise ValueError("max_stocks_per_member must be >= 1")


DEFAULT_CONFIG = StockConfig()


def format_cash(minor: int, config: StockConfig = DEFAULT_CONFIG) -> str:
    """Format integer minor units as a display string."""
    sign = "-" if minor < 0 else ""
    abs_minor = abs(int(minor))
    precision = config.currency_precision
    divisor = 10 ** precision
    whole = abs_minor // divisor
    frac = abs_minor % divisor
    return f"{sign}{config.currency_symbol}{whole:,}.{frac:0{precision}d}"
