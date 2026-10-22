import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


UP_COLOR = "#2ecc71"
DOWN_COLOR = "#e74c3c"
FLAT_COLOR = "#95a5a6"

CANDLE_UP = "#26a69a"
CANDLE_DOWN = "#ef5350"
CHART_BG = "#131722"
GRID_COLOR = "#2a2e39"

CANDLE_MIN_POINTS = 12
MAX_CANDLES = 30


def use_candles(n_points: int) -> bool:
    """True when history is dense enough for meaningful candle bodies."""
    return n_points >= CANDLE_MIN_POINTS


def _save(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none", dpi=180)
    plt.close(fig)
    buf.seek(0)
    return buf


def movement_colors(prices: list[float], up: str = UP_COLOR, down: str = DOWN_COLOR) -> list[str]:
    """Per-segment colors: up where the price rose (or held), down where it fell.

    Returns one color per consecutive pair, so ``len(result) == len(prices) - 1``.
    Pure helper kept separate for unit tests.
    """
    colors = []
    for prev, curr in zip(prices, prices[1:]):
        colors.append(up if curr >= prev else down)
    return colors


def price_chart(timestamps: list[float], prices_minor: list[float], ticker: str,
                symbol: str = "₹", trades: list[dict] | None = None,
                force_line: bool = False) -> io.BytesIO:
    """Dark-mode price chart, TradingView-style.

    Dense history (>= ``CANDLE_MIN_POINTS`` points) renders as
    candlesticks; sparse history renders as a teal/red segmented line,
    since one-point candles would just be flat dashes. When ``trades``
    are given, a bottom panel shows buy (teal) vs sell (red) shares
    per candle/point; with no trades only the price panel is drawn.
    Set ``force_line`` to always render the segmented line (used for
    the ``.stock info`` graph).
    """
    with plt.style.context("dark_background"):
        fig = plt.figure(figsize=(8, 5), facecolor=CHART_BG)
        if not force_line and use_candles(len(prices_minor)):
            _candle_axes(fig, timestamps, prices_minor, trades, ticker, symbol)
        else:
            _line_axes(fig, timestamps, prices_minor, trades, ticker, symbol)
        return _save(fig)


def _style_axis(ax, *, ylabel: str) -> None:
    ax.set_facecolor(CHART_BG)
    ax.set_ylabel(ylabel, color="white")
    ax.grid(color=GRID_COLOR, alpha=0.9)
    ax.tick_params(colors="white")
    ax.margins(y=0.25)


def _candle_axes(fig, timestamps: list[float], prices_minor: list[float],
                 trades: list[dict] | None, ticker: str, symbol: str) -> None:
    """Candlesticks for dense history, plus a buy/sell bar panel."""
    import datetime as dt

    from .statistics import candles, side_volumes

    bars = candles(timestamps, [p / 100.0 for p in prices_minor], max_candles=MAX_CANDLES)
    buys, sells = side_volumes(timestamps, trades, MAX_CANDLES)
    buys = buys[:len(bars)]
    sells = sells[:len(bars)]
    show_side = bool(bars) and any(b > 0 for b in buys + sells)
    if show_side:
        ax, ax_vol = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    else:
        ax = fig.subplots()
        ax_vol = None
    xs = list(range(len(bars)))
    width = 0.6
    if not bars:
        ax.set_title(f"{ticker} ({symbol})", color="white")
        _style_axis(ax, ylabel=f"price ({symbol})")
        ax.text(0.5, 0.5, "no data yet", ha="center", transform=ax.transAxes, color="white")
        ax.set_xlabel("time", color="white")
        return
    ax.set_title(f"{ticker} ({symbol})", color="white")
    _style_axis(ax, ylabel=f"price ({symbol})")
    for x, b in zip(xs, bars):
        color = CANDLE_UP if b["close"] >= b["open"] else CANDLE_DOWN
        ax.plot([x, x], [b["low"], b["high"]], color=color, linewidth=1.2)
        body = abs(b["close"] - b["open"])
        if body == 0:
            ax.plot([x - width / 2, x + width / 2], [b["close"], b["close"]],
                    color=color, linewidth=2)
        else:
            ax.bar(x, body, bottom=min(b["open"], b["close"]),
                   width=width, color=color, edgecolor=color, linewidth=1.2)
    span = bars[-1]["ts"] - bars[0]["ts"] if len(bars) > 1 else 0
    fmt = "%H:%M" if span < 2 * 86400 else "%m-%d"
    ticks = sorted({xs[i * len(xs) // 5] for i in range(5)} | {xs[-1]}) if len(xs) > 1 else xs
    ax.set_xticks(ticks)
    ax.set_xticklabels([dt.datetime.fromtimestamp(bars[i]["ts"]).strftime(fmt) for i in ticks])
    if ax_vol is not None:
        _style_axis(ax_vol, ylabel="buy/sell shares")
        _side_bars(ax_vol, xs, buys, sells, width=width / 2, gap=width / 2)
        ax_vol.set_xlabel("time", color="white")
    else:
        ax.set_xlabel("time", color="white")


def _side_bars(ax, xs: list, buys: list[float], sells: list[float], width: float, gap: float) -> None:
    """Grouped buy (teal) vs sell (red) bars centered on ``xs``."""
    ax.bar([x - gap / 2 for x in xs], buys, width=width, color=CANDLE_UP, alpha=0.9)
    ax.bar([x + gap / 2 for x in xs], sells, width=width, color=CANDLE_DOWN, alpha=0.9)


def _line_axes(fig, timestamps: list[float], prices_minor: list[float],
               trades: list[dict] | None, ticker: str, symbol: str) -> None:
    """Segmented teal/red line for sparse history, plus a buy/sell bar panel."""
    import datetime as dt

    from .statistics import side_volumes

    buys, sells = side_volumes(timestamps, trades, max_candles=max(len(timestamps), 1))
    show_side = bool(prices_minor) and any(b > 0 for b in buys + sells)
    if show_side:
        ax, ax_vol = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    else:
        ax = fig.subplots()
        ax_vol = None
    ax.set_title(f"{ticker} ({symbol})", color="white")
    _style_axis(ax, ylabel=f"price ({symbol})")
    if not prices_minor:
        ax.text(0.5, 0.5, "no data yet", ha="center", transform=ax.transAxes, color="white")
    elif len(prices_minor) == 1:
        ax.scatter([dt.datetime.fromtimestamp(timestamps[0])], [prices_minor[0] / 100.0],
                   color=CANDLE_UP, s=60, zorder=5)
    else:
        dates = [dt.datetime.fromtimestamp(t) for t in timestamps]
        values = [p / 100.0 for p in prices_minor]
        seg_colors = movement_colors(values, up=CANDLE_UP, down=CANDLE_DOWN)
        for (x0, y0), (x1, y1), color in zip(zip(dates, values), zip(dates[1:], values[1:]),
                                             seg_colors):
            ax.plot([x0, x1], [y0, y1], color=color, linewidth=2.5)
        ax.scatter([dates[-1]], [values[-1]],
                   color=CANDLE_UP if values[-1] >= values[0] else CANDLE_DOWN,
                   s=60, zorder=5)
        fig.autofmt_xdate()
    if ax_vol is not None:
        import matplotlib.dates as mdates

        nums = mdates.date2num(dates)
        gaps = [b - a for a, b in zip(nums, nums[1:]) if b > a]
        step = (sorted(gaps)[len(gaps) // 2]) if gaps else 0.02
        _style_axis(ax_vol, ylabel="buy/sell shares")
        _side_bars(ax_vol, nums, buys[:len(nums)], sells[:len(nums)],
                   width=step * 0.3, gap=step * 0.3)
        ax_vol.set_xlabel("time", color="white")
    else:
        ax.set_xlabel("time", color="white")


def allocation_chart(labels: list[str], values: list[float], title: str = "Portfolio") -> io.BytesIO:
    """Dark-mode donut chart for portfolio allocation — beautiful on Discord."""
    # vibrant but harmonious palette that pops on CHART_BG
    PALETTE = ["#00E5A0", "#38BDF8", "#FB7185", "#FACC15", "#A78BFA", "#2DD4BF", "#FB923C", "#4ADE80", "#F472B6", "#60A5FA"]

    with plt.style.context("dark_background"):
        fig, ax = plt.subplots(figsize=(6.4, 4.2), facecolor=CHART_BG)
        ax.set_facecolor(CHART_BG)
        ax.set_title(title, color="white", fontsize=13, weight=600, pad=18, fontfamily="sans-serif")

        if not values or sum(values) <= 0:
            ax.text(0.5, 0.5, "no holdings", ha="center", va="center", transform=ax.transAxes, color="#9CA3AF", fontsize=11)
            ax.axis("off")
            return _save(fig)

        colors = [PALETTE[i % len(PALETTE)] for i in range(len(values))]
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.82,
            wedgeprops=dict(width=0.46, edgecolor=CHART_BG, linewidth=2.8),
            textprops=dict(color="#E5E7EB", fontsize=9.2),
        )
        for t in texts:
            t.set_fontsize(9.2)
            t.set_color("#E5E7EB")
        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(8.6)
            at.set_weight(700)
            at.set_path_effects([])

        ax.axis("equal")
        # subtle center label
        ax.text(0, 0, f"{len(values)}\nassets", ha="center", va="center", color="#9CA3AF", fontsize=8, linespacing=1.1, weight=600)
        return _save(fig)


def movers_chart(labels: list[str], changes_pct: list[float], title: str = "Movers %") -> io.BytesIO:
    """Dark-mode beautified bar chart of gainers/losers percentage changes."""
    with plt.style.context("dark_background"):
        fig, ax = plt.subplots(figsize=(8, 4.2), facecolor=CHART_BG)
        ax.set_facecolor(CHART_BG)
        ax.set_title(title, color="white", fontsize=13, weight=600, pad=16)
        ax.set_ylabel("% change", color="#9CA3AF", fontsize=9)
        ax.grid(axis="y", color=GRID_COLOR, alpha=0.6, linestyle="--", linewidth=0.6)
        ax.set_axisbelow(True)
        # styled ticks
        ax.tick_params(colors="#E5E7EB", labelsize=8.5, axis="x", rotation=18)
        ax.tick_params(colors="#9CA3AF", labelsize=8.5, axis="y")

        # spine styling
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)

        if not labels:
            ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes, color="#9CA3AF", fontsize=11)
            # hide ticks
            ax.set_xticks([])
            return _save(fig)

        values = [c * 100.0 for c in changes_pct]
        colors = [CANDLE_UP if c >= 0 else CANDLE_DOWN for c in changes_pct]
        # rounded-ish bars with edge
        bars = ax.bar(labels, values, color=colors, edgecolor=CHART_BG, linewidth=1.2, width=0.62, zorder=3)
        # value labels on bars
        ymax = max(values) if values else 1
        ymin = min(values) if values else -1
        ypad = max(abs(ymax), abs(ymin), 1) * 0.08
        for bar, val in zip(bars, values):
            y = bar.get_height()
            txt = f"{val:+.2f}%"
            color = "white"
            # place slightly above positive, below negative
            va = "bottom" if y >= 0 else "top"
            offset = 3 if y >= 0 else -3
            ax.text(bar.get_x() + bar.get_width() / 2, y + (ypad * 0.15 if y >= 0 else -ypad * 0.15),
                    txt, ha="center", va=va, color=color, fontsize=8, weight=700)

        # zero line
        ax.axhline(0, color="#4B5563", linewidth=1, zorder=2)
        # tighten y limits with padding
        ax.margins(y=0.18)
        # no x label needed
        return _save(fig)
