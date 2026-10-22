"""Pure, deterministic price/activity formulas (no Discord or DB I/O).

All functions are pure: same inputs produce same outputs. Randomness
must be injected by the caller (see ``baseline_return``) so tests are
deterministic.

Conventions:
- Activity scores are normalized to ``[0, 1]`` with diminishing returns
  via ``min(1, count / target)``. Holder aggregates cap each member
  before summing so one spammer or a large crowd cannot force
  unlimited growth.
- Owner messages count only in the owner signal, never again in the
  holder aggregate (caller must exclude the owner from holder counts).
- Inactivity decay is time-based (``exp(-rate * elapsed) - 1``) so the
  result does not depend on how often the updater runs.
- Trade impact is signed value relative to liquidity, clamped per trade.
- Scheduled updates clamp the combined return; trades use the larger
  ``max_trade_move`` cap only at execution time. Never count the same
  trade in both places.
"""

import math
from typing import Iterable, Mapping

from .models import PriceBreakdown, TradeQuote


def normalize_score(count: int, target: int) -> float:
    """Normalize a qualifying-activity count to ``[0, 1]`` with a cap."""
    if target < 1:
        raise ValueError("target must be >= 1")
    if count <= 0:
        return 0.0
    return min(1.0, count / target)


def holder_aggregate_score(
    per_member_counts: Iterable[int],
    per_member_cap: int,
    aggregate_target: int,
) -> float:
    """Aggregate holder activity with per-member diminishing returns.

    Each member contributes ``min(count, per_member_cap)``; the sum is
    then normalized against ``aggregate_target`` and capped at 1.0.
    """
    if per_member_cap < 1:
        raise ValueError("per_member_cap must be >= 1")
    if aggregate_target < 1:
        raise ValueError("aggregate_target must be >= 1")
    capped_total = sum(min(max(0, c), per_member_cap) for c in per_member_counts)
    return min(1.0, capped_total / aggregate_target)


def owner_activity_return(
    score: float,
    hours_since_active: float | None,
    max_return: float,
    stale_horizon_hours: float,
) -> float:
    """Owner signal in ``[-0.1 * max_return, +max_return]``.

    Fresh + fully active -> ``+max_return``. Fully stale
    (``hours_since_active >= stale_horizon_hours`` or ``None``) ->
    ``-0.1 * max_return`` — a small drag, never a crash. Linear
    freshness interpolation between. The stale drag is deliberately
    tiny so a quiet stock decays gradually (≈ time-decay dominated)
    instead of collapsing when its owner goes offline for days.
    """
    if not 0.0 <= score <= 1.0:
        raise ValueError("score must be within [0, 1]")
    if max_return < 0:
        raise ValueError("max_return cannot be negative")
    if stale_horizon_hours <= 0:
        raise ValueError("stale_horizon_hours must be positive")
    if hours_since_active is None:
        freshness = 0.0
    else:
        freshness = max(0.0, 1.0 - max(0.0, hours_since_active) / stale_horizon_hours)
    return max_return * (score * freshness - (1.0 - freshness) * 0.1)


def holder_activity_return(
    score: float,
    hours_since_active: float | None,
    max_return: float,
    stale_horizon_hours: float,
) -> float:
    """Holder signal, same shape as owner but with a smaller cap."""
    return owner_activity_return(score, hours_since_active, max_return, stale_horizon_hours)


def inactivity_decay_return(elapsed_seconds: float, decay_per_day: float) -> float:
    """Time-based decay ``exp(-rate * days) - 1`` (always ``<= 0``)."""
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds cannot be negative")
    if decay_per_day < 0:
        raise ValueError("decay_per_day cannot be negative")
    elapsed_days = elapsed_seconds / 86_400.0
    return math.exp(-decay_per_day * elapsed_days) - 1.0


def trade_impact_return(
    signed_value_minor: int,
    liquidity_minor: int,
    sensitivity: float,
    minimum_liquidity_minor: int,
    max_abs_move: float,
) -> float:
    """Signed trade pressure, clamped to ``[-max_abs_move, +max_abs_move]``.

    Positive value (buy) -> positive impact; negative (sell) -> negative.
    Impact scales with value relative to liquidity, not raw quantity.
    """
    if sensitivity < 0:
        raise ValueError("sensitivity cannot be negative")
    if minimum_liquidity_minor < 1:
        raise ValueError("minimum_liquidity_minor must be >= 1")
    if max_abs_move <= 0:
        raise ValueError("max_abs_move must be positive")
    denominator = max(int(liquidity_minor), int(minimum_liquidity_minor))
    if denominator <= 0:
        raise ValueError("liquidity must be positive after floor")
    raw = sensitivity * (int(signed_value_minor) / denominator)
    return max(-max_abs_move, min(max_abs_move, raw))


def baseline_return(rand_minus1_1: float, vol: float) -> float:
    """Tiny bounded noise; caller injects the random value for tests."""
    if not -1.0 <= rand_minus1_1 <= 1.0:
        raise ValueError("rand_minus1_1 must be within [-1, 1]")
    if vol < 0:
        raise ValueError("vol cannot be negative")
    return rand_minus1_1 * vol


def clamp_return(value: float, max_abs_move: float) -> float:
    """Clamp a fractional return to ``[-max_abs_move, +max_abs_move]``."""
    if max_abs_move <= 0:
        raise ValueError("max_abs_move must be positive")
    return max(-max_abs_move, min(max_abs_move, value))


def apply_return_to_price(
    old_price_minor: int,
    fractional_return: float,
    min_price_minor: int,
    max_price_minor: int,
) -> int:
    """Apply a fractional return, round to minor units, enforce floor/ceiling."""
    if old_price_minor <= 0:
        raise ValueError("old_price_minor must be positive")
    if not 1 <= min_price_minor < max_price_minor:
        raise ValueError("require 1 <= min_price < max_price")
    if math.isnan(fractional_return) or math.isinf(fractional_return):
        raise ValueError("fractional_return must be finite")
    new_price = int(round(old_price_minor * (1.0 + fractional_return)))
    return max(min_price_minor, min(max_price_minor, new_price))


def combine_returns(
    old_price_minor: int,
    owner_component: float,
    holder_component: float,
    inactivity_component: float,
    trade_component: float,
    baseline_component: float,
    max_abs_move: float,
    min_price_minor: int,
    max_price_minor: int,
) -> PriceBreakdown:
    """Combine signals with a cap, settle the price, return a breakdown."""
    raw = (
        owner_component
        + holder_component
        + inactivity_component
        + trade_component
        + baseline_component
    )
    if math.isnan(raw) or math.isinf(raw):
        raise ValueError("combined return must be finite")
    clamped = clamp_return(raw, max_abs_move)
    new_price = apply_return_to_price(
        old_price_minor, clamped, min_price_minor, max_price_minor
    )
    return PriceBreakdown(
        owner_component=owner_component,
        holder_component=holder_component,
        inactivity_component=inactivity_component,
        trade_component=trade_component,
        baseline_component=baseline_component,
        raw_return=raw,
        clamped_return=clamped,
        old_price_minor=old_price_minor,
        new_price_minor=new_price,
    )


def quote_trade(
    quantity: int,
    execution_price_minor: int,
    fee_rate: float,
    is_buy: bool,
) -> TradeQuote:
    """Quote a market order from a consistent pre-trade price (int math)."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if execution_price_minor <= 0:
        raise ValueError("execution_price_minor must be positive")
    if not 0 <= fee_rate <= 0.05:
        raise ValueError("fee_rate must be within [0, 5%]")
    gross = int(quantity) * int(execution_price_minor)
    fee = int(round(gross * fee_rate))
    total = gross + fee if is_buy else gross - fee
    if total < 0:
        raise ValueError("net proceeds cannot be negative")
    return TradeQuote(
        quantity=quantity,
        execution_price_minor=execution_price_minor,
        gross_minor=gross,
        fee_minor=fee,
        total_minor=total,
        is_buy=is_buy,
    )


def score_activity_window(
    owner_count: int,
    holder_counts: Mapping[int, int] | Iterable[int],
    owner_target: int,
    holder_target: int,
    holder_per_member_cap: int,
) -> tuple[float, float]:
    """Convenience: normalize owner + holder counts for one window.

    ``holder_counts`` may be a mapping of user_id -> count or an
    iterable of counts. Caller must already exclude the owner and
    enforce cooldowns/anti-spam; this function only normalizes.
    """
    owner_score = normalize_score(owner_count, owner_target)
    if isinstance(holder_counts, Mapping):
        counts = list(holder_counts.values())
    else:
        counts = list(holder_counts)
    holder_score = holder_aggregate_score(counts, holder_per_member_cap, holder_target)
    return owner_score, holder_score
