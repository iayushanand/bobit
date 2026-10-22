"""Domain structures for the simulated stock market.

Money is stored as integer minor units. Timestamps are epoch seconds
(float) so pricing stays free of Discord/DB types.
"""

from dataclasses import dataclass, field
from typing import Any


STATUS_ACTIVE = "active"
STATUS_HALTED = "halted"
STATUS_DELISTED = "delisted"
VALID_STATUSES = (STATUS_ACTIVE, STATUS_HALTED, STATUS_DELISTED)


@dataclass(frozen=True)
class PriceBreakdown:
    """Component returns (fractions) plus settlement result."""

    owner_component: float = 0.0
    holder_component: float = 0.0
    inactivity_component: float = 0.0
    trade_component: float = 0.0
    baseline_component: float = 0.0
    raw_return: float = 0.0
    clamped_return: float = 0.0
    old_price_minor: int = 0
    new_price_minor: int = 0


@dataclass(frozen=True)
class TradeQuote:
    """Pure settlement quote for a market order at a pre-trade price."""

    quantity: int = 0
    execution_price_minor: int = 0
    gross_minor: int = 0
    fee_minor: int = 0
    total_minor: int = 0  # buy: gross + fee (charged); sell: gross - fee (proceeds)
    is_buy: bool = True


@dataclass(frozen=True)
class TradeReceipt:
    """Result of a settled trade."""

    ticker: str = ""
    quantity: int = 0
    execution_price_minor: int = 0
    gross_minor: int = 0
    fee_minor: int = 0
    total_minor: int = 0
    new_price_minor: int = 0
    is_buy: bool = True


@dataclass
class StockState:
    """Minimal price state needed by Phase 1 pure functions."""

    ticker: str = ""
    current_price_minor: int = 0
    last_price_update_at: float = 0.0
    extra: dict = field(default_factory=dict)


def new_stock_doc(
    guild_id: int | None = None,
    owner_id: int | None = None,
    ticker: str = "",
    name: str = "",
    price_minor: int = 0,
    total_shares: int = 0,
    creator_allocation: int = 0,
    now: float = 0.0,
    description: str = "",
) -> dict[str, Any]:
    """Build a stock document. Caller inserts it and creates holdings.

    ``guild_id`` is retained for backwards compatibility but stocks are
    now global: the stored ``guild_id`` is always ``0`` (global sentinel)
    regardless of the caller-provided value.
    """
    available = int(total_shares) - int(creator_allocation)
    return {
        "guild_id": 0,
        "owner_user_id": int(owner_id) if owner_id is not None else 0,
        "ticker": ticker,
        "name": name,
        "description": description[:500] if isinstance(description, str) else "",
        "current_price": int(price_minor),
        "initial_price": int(price_minor),
        "total_shares": int(total_shares),
        "available_shares": int(available),
        "liquidity": int(price_minor) * int(available),
        "created_at": float(now),
        "last_price_update_at": float(now),
        "last_owner_activity_at": float(now),
        "status": STATUS_ACTIVE,
    }


def liquidity_for(price_minor: int, available_shares: int, minimum: int) -> int:
    """Market-depth proxy: price * available, floored at minimum."""
    return max(int(minimum), int(price_minor) * max(0, int(available_shares)))
