import time
from collections import defaultdict


class ActivityTracker:
    """In-memory cooldown + eligibility helpers (cheap per-message path)."""

    def __init__(self, cooldown_seconds: int = 45) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_seen: dict[int, float] = {}

    def is_qualifying_message(self, content: str, is_bot: bool, is_webhook: bool,
                              channel_id: int, excluded_channels: tuple,
                              command_prefixes: tuple = (".",)) -> bool:
        """Cheap synchronous filter; no DB access."""
        if is_bot or is_webhook:
            return False
        if channel_id in (excluded_channels or ()):
            return False
        text = (content or "").strip()
        if not text:
            return False
        if text.startswith(command_prefixes or (".",)):
            return False
        return True

    def check_cooldown(self, user_id: int, now: float | None = None) -> bool:
        """True if the user may be scored now; records the hit."""
        now = time.time() if now is None else now
        last = self._last_seen.get(user_id, 0.0)
        if now - last < self.cooldown_seconds:
            return False
        self._last_seen[user_id] = now
        return True


def aggregate_window(counts_by_user: dict[int, int], owner_id: int,
                     per_member_cap: int) -> tuple[int, dict[int, int]]:
    """Split an owner count from holder counts (owner excluded from holders)."""
    owner_count = int(counts_by_user.get(owner_id, 0))
    holders = {u: min(c, per_member_cap) for u, c in counts_by_user.items()
               if u != owner_id and c > 0}
    return owner_count, holders


def count_events(events: list[dict]) -> dict[int, int]:
    """Count activity docs per user (docs carry only ts/ids, no bodies)."""
    counts: dict[int, int] = defaultdict(int)
    for e in events:
        counts[int(e["user_id"])] += 1
    return dict(counts)
