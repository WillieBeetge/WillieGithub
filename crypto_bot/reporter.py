"""Format and persist prediction reports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from crypto_bot import config
from crypto_bot.analyzer import Prediction

console = Console()


def _timestamp_sast() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def _fmt_price(value: float) -> str:
    if value >= 1:
        return f"${value:,.4f}".rstrip("0").rstrip(".")
    if value >= 0.01:
        return f"${value:.6f}".rstrip("0").rstrip(".")
    return f"${value:.8f}"


def format_report(
    predictions: list[Prediction], generated_at: datetime | None = None
) -> str:
    when = generated_at or _timestamp_sast()
    lines = [
        "=" * 72,
        "SA CRYPTO PREDICTION BOT — Top 5 setups (target gain 10–30%)",
        f"Generated: {when.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "Disclaimer: Not financial advice. Crypto is high risk. DYOR.",
        "=" * 72,
        "",
    ]
    for p in predictions:
        lines.extend(
            [
                f"#{p.rank}  {p.symbol}  ({p.name})",
                f"    Spot: {_fmt_price(p.price_usd)}  |  Pred. gain: +{p.predicted_gain_pct}%",
                f"    Probability: {p.probability_pct:.0f}% overall  |  "
                f"TP1 {p.probability_tp1_pct:.0f}%  |  TP2 {p.probability_tp2_pct:.0f}%",
                f"    Best time to trade: {p.best_time_sast}",
                f"      ({p.best_time_reason})",
                f"    TRADE SUGGESTION (long)",
                f"      Entry : {_fmt_price(p.entry_usd)}  ({p.entry_note})",
                f"      TP1   : {_fmt_price(p.tp1_usd)}  (R:R {p.risk_reward_tp1:.2f})",
                f"      TP2   : {_fmt_price(p.tp2_usd)}  (R:R {p.risk_reward_tp2:.2f})",
                f"      SL    : {_fmt_price(p.sl_usd)}",
                f"    Confidence: {p.confidence:.0%}  |  Score: {p.score:.3f}",
                f"    24h: {p.change_24h_pct:+.2f}%  |  7d: {p.change_7d_pct:+.2f}%  "
                f"|  RSI: {p.rsi_14}  |  Vol: {p.volatility_14d_pct}%",
                f"    Why: {p.reason}",
                "",
            ]
        )
    lines.append("Next scheduled runs: 06:00 and 16:00 Africa/Johannesburg")
    return "\n".join(lines)


def print_report(
    predictions: list[Prediction], generated_at: datetime | None = None
) -> None:
    when = generated_at or _timestamp_sast()
    table = Table(
        title=f"Top 5 crypto setups — {when.strftime('%Y-%m-%d %H:%M %Z')}",
        show_lines=True,
    )
    table.add_column("#", justify="right", style="bold")
    table.add_column("Coin")
    table.add_column("Prob%", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("TP1", justify="right")
    table.add_column("TP2", justify="right")
    table.add_column("SL", justify="right")
    table.add_column("Best time (SAST)")

    for p in predictions:
        table.add_row(
            str(p.rank),
            f"{p.symbol}\n{p.name}",
            f"{p.probability_pct:.0f}%\nTP1 {p.probability_tp1_pct:.0f}%",
            _fmt_price(p.entry_usd),
            _fmt_price(p.tp1_usd),
            _fmt_price(p.tp2_usd),
            _fmt_price(p.sl_usd),
            p.best_time_sast,
        )

    console.print(
        Panel.fit(
            "Heuristic long setups with Entry / TP1 / TP2 / SL, probability %, "
            "and best SAST trade window.\n"
            "[bold red]Not financial advice.[/] Probabilities are model estimates, "
            "not guarantees.",
            title="SA Crypto Prediction Bot",
        )
    )
    console.print(table)

    for p in predictions:
        console.print(
            f"  [bold]#{p.rank} {p.symbol}[/] "
            f"prob {p.probability_pct:.0f}% (TP1 {p.probability_tp1_pct:.0f}% / "
            f"TP2 {p.probability_tp2_pct:.0f}%) — {p.best_time_sast}"
        )
        console.print(f"    {p.best_time_reason}")
        console.print(f"    {p.entry_note} — {p.reason}")


def save_report(
    predictions: list[Prediction], generated_at: datetime | None = None
) -> Path:
    when = generated_at or _timestamp_sast()
    stamp = when.strftime("%Y%m%d_%H%M%S")
    base = config.OUTPUT_DIR / f"predictions_{stamp}"

    payload = {
        "generated_at": when.isoformat(),
        "timezone": config.TIMEZONE,
        "target_gain_band_pct": [config.MIN_GAIN_PCT, config.MAX_GAIN_PCT],
        "trade_windows_sast": {
            "primary": config.PRIMARY_TRADE_WINDOW_SAST,
            "secondary": config.SECONDARY_TRADE_WINDOW_SAST,
        },
        "disclaimer": (
            "Not financial advice. Probability % is a heuristic estimate only."
        ),
        "predictions": [p.to_dict() for p in predictions],
    }

    json_path = base.with_suffix(".json")
    txt_path = base.with_suffix(".txt")
    latest_json = config.OUTPUT_DIR / "latest.json"
    latest_txt = config.OUTPUT_DIR / "latest.txt"

    text = format_report(predictions, when)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    txt_path.write_text(text, encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_txt.write_text(text, encoding="utf-8")
    return json_path
