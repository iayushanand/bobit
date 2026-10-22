"""Input validation for stock commands."""

import re

from .exceptions import ValidationError

TICKER_RE = re.compile(r"^[A-Z0-9]{2,8}$")


def normalize_ticker(raw: str) -> str:
    """Uppercase, strip, validate 2-8 alphanumerics. Raises ValidationError."""
    ticker = (raw or "").strip().upper()
    if not TICKER_RE.match(ticker):
        raise ValidationError("Ticker must be 2-8 letters/numbers (e.g. `BIT`).")
    return ticker


def validate_name(name: str) -> str:
    """Trim and validate display name (3-32 chars)."""
    clean = " ".join((name or "").split())
    if not 3 <= len(clean) <= 32:
        raise ValidationError("Name must be 3-32 characters.")
    return clean


def validate_description(description: str | None) -> str:
    """Trim description to 500 chars (may be empty)."""
    if not description:
        return ""
    return " ".join(description.split())[:500]


def validate_quantity(qty: int) -> int:
    """Must be a positive integer within a sane bound."""
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValidationError("Quantity must be a whole number.")
    if not 1 <= qty <= 1_000_000:
        raise ValidationError("Quantity must be between 1 and 1,000,000.")
    return qty


def validate_price_alert(price: float) -> float:
    if price <= 0:
        raise ValidationError("Alert price must be positive.")
    return float(price)
