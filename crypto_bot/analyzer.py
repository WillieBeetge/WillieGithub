"""Score coins for plausible short-term 10–30% upside setups."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from crypto_bot import config


@dataclass
class Prediction:
    rank: int
    symbol: str
    name: str
    coin_id: str
    price_usd: float
    predicted_gain_pct: float
    target_price_usd: float
    entry_usd: float
    tp1_usd: float
    tp2_usd: float
    sl_usd: float
    entry_note: str
    risk_reward_tp1: float
    risk_reward_tp2: float
    probability_pct: float
    probability_tp1_pct: float
    probability_tp2_pct: float
    best_time_sast: str
    best_time_reason: str
    confidence: float
    score: float
    reason: str
    volume_24h_usd: float
    change_24h_pct: float
    change_7d_pct: float
    rsi_14: float
    volatility_14d_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _round_price(value: float) -> float:
    if value >= 100:
        return round(value, 2)
    if value >= 1:
        return round(value, 4)
    if value >= 0.01:
        return round(value, 6)
    return round(value, 8)


def _trade_levels(
    price: float,
    predicted_gain_pct: float,
    close: pd.Series,
    vol_ann_pct: float,
) -> dict[str, float | str | bool]:
    """Build long-biased Entry / TP1 / TP2 / SL from price action + vol."""
    recent = close.tail(14)
    recent_low = float(recent.min()) if not recent.empty else price * 0.95

    daily_move_pct = max(vol_ann_pct / (365**0.5), 1.5)
    pullback_pct = min(max(daily_move_pct * 0.35, 0.8), 4.0)
    stop_pct = min(max(daily_move_pct * 1.1, 3.0), 12.0)

    near_low = price <= recent_low * 1.03
    if near_low:
        entry = price
        entry_note = "market entry (near recent low)"
    else:
        entry = price * (1 - pullback_pct / 100.0)
        entry = max(entry, recent_low * 1.005)
        entry_note = f"limit buy ~{pullback_pct:.1f}% below spot"

    tp1_pct = max(predicted_gain_pct * 0.45, config.MIN_GAIN_PCT * 0.6)
    tp2_pct = predicted_gain_pct
    tp1 = entry * (1 + tp1_pct / 100.0)
    tp2 = entry * (1 + tp2_pct / 100.0)

    structure_sl = recent_low * 0.985
    vol_sl = entry * (1 - stop_pct / 100.0)
    sl = min(structure_sl, vol_sl)
    sl = min(sl, entry * 0.97)
    sl = max(sl, entry * 0.88)

    risk = entry - sl
    rr1 = (tp1 - entry) / risk if risk > 0 else 0.0
    rr2 = (tp2 - entry) / risk if risk > 0 else 0.0

    return {
        "entry_usd": _round_price(entry),
        "tp1_usd": _round_price(tp1),
        "tp2_usd": _round_price(tp2),
        "sl_usd": _round_price(sl),
        "entry_note": entry_note,
        "risk_reward_tp1": round(rr1, 2),
        "risk_reward_tp2": round(rr2, 2),
        "near_low": near_low,
    }


def _probability_pcts(
    raw_score: float,
    rsi: float,
    surge: float,
    bounce: float,
    rr1: float,
    predicted_gain_pct: float,
) -> tuple[float, float, float]:
    """Heuristic % chance of a favourable outcome (not a calibrated forecast)."""
    base = 28.0 + raw_score * 42.0  # roughly 28–70 from score alone

    if 35 <= rsi <= 55:
        base += 6.0
    elif rsi < 35:
        base += 4.0
    elif rsi > 70:
        base -= 8.0

    if surge >= 1.25:
        base += 5.0
    if bounce < 10:
        base += 4.0
    elif bounce > 25:
        base -= 6.0

    if rr1 >= 2.0:
        base += 3.0

    stretch = max(predicted_gain_pct - 15.0, 0.0) * 0.35
    overall = min(max(base - stretch * 0.35, 18.0), 78.0)
    tp1 = min(max(overall + 8.0, 22.0), 82.0)
    tp2 = min(max(overall - 12.0 - stretch, 12.0), 65.0)
    return round(overall, 1), round(tp1, 1), round(tp2, 1)


def _best_trade_time(
    entry_note: str,
    near_low: bool,
    vol_ann_pct: float,
    volume_24h: float,
) -> tuple[str, str]:
    """Recommend a SAST window when fills/slippage are typically better."""
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    hour = now.hour

    primary = config.PRIMARY_TRADE_WINDOW_SAST
    secondary = config.SECONDARY_TRADE_WINDOW_SAST
    needs_deep_book = vol_ann_pct >= 90 or volume_24h < 20_000_000

    if 16 <= hour < 20:
        window = f"Now–20:00 SAST (in prime window) · else next {primary}"
        reason = (
            "Currently inside the prime SAST liquidity window (EU/US overlap). "
            "Act on the plan now; otherwise wait for the next 16:00–20:00 SAST slot."
        )
    elif 8 <= hour < 11:
        window = f"Now–11:00 SAST (London open) · or wait for {primary}"
        reason = (
            "London-open liquidity is decent in SAST morning. "
            f"For the strongest book, still favour {primary}."
        )
    elif near_low or "market entry" in entry_note:
        window = primary if needs_deep_book else f"{primary} (or {secondary})"
        reason = (
            "Market-style entry — prefer EU/US overlap for tighter spreads "
            f"({primary}); London open ({secondary}) is a solid backup."
        )
    else:
        window = f"Place limit now; expect fill {primary}"
        reason = (
            "Limit pullback entry can sit anytime, but fills and follow-through "
            f"are usually strongest during {primary} (EU/US overlap)."
        )

    return window, reason


def _series_from_chart(chart: dict[str, Any], key: str) -> pd.Series:
    rows = chart.get(key) or []
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    vals = pd.Series([float(r[1]) for r in rows], index=idx, dtype=float)
    return vals[~vals.index.duplicated(keep="last")].sort_index()


def _rsi(close: pd.Series, period: int = 14) -> float:
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    value = float(rsi.iloc[-1])
    return value if np.isfinite(value) else 50.0


def _realized_vol_pct(close: pd.Series, window: int = 14) -> float:
    if len(close) < window + 1:
        return 0.0
    rets = np.log(close / close.shift(1)).dropna()
    vol = float(rets.tail(window).std() * np.sqrt(365) * 100)
    return vol if np.isfinite(vol) else 0.0


def _distance_from_low_pct(close: pd.Series, lookback: int = 14) -> float:
    window = close.tail(lookback)
    if window.empty or window.min() <= 0:
        return 0.0
    return float((window.iloc[-1] / window.min() - 1.0) * 100)


def _volume_surge(volume: pd.Series) -> float:
    if len(volume) < 8:
        return 1.0
    recent = float(volume.tail(3).mean())
    base = float(volume.tail(14).mean()) or 1.0
    return recent / base


def score_coin(market: dict[str, Any], chart: dict[str, Any]) -> Prediction | None:
    """Return a scored prediction or None if the coin is not a fit."""
    volume_24h = float(market.get("total_volume") or 0)
    if volume_24h < config.MIN_24H_VOLUME_USD:
        return None

    price = float(market.get("current_price") or 0)
    if price <= 0:
        return None

    close = _series_from_chart(chart, "prices")
    volume = _series_from_chart(chart, "total_volumes")
    if len(close) < 16:
        return None

    change_24h = float(market.get("price_change_percentage_24h") or 0)
    change_7d = float(
        market.get("price_change_percentage_7d_in_currency")
        or market.get("price_change_percentage_7d")
        or 0
    )
    change_14d = float(market.get("price_change_percentage_14d_in_currency") or 0)

    rsi = _rsi(close)
    vol = _realized_vol_pct(close)
    bounce = _distance_from_low_pct(close)
    surge = _volume_surge(volume)

    volatility_fit = 1.0 - min(abs(vol - 80.0) / 80.0, 1.0)
    rsi_fit = 1.0 - min(abs(rsi - 45.0) / 45.0, 1.0)
    not_extended = max(0.0, 1.0 - bounce / 35.0)
    momentum = 0.0
    if change_24h > 0:
        momentum += min(change_24h / 8.0, 1.0)
    if -5 <= change_7d <= 20:
        momentum += 0.5
    if change_14d < 40:
        momentum += 0.25
    volume_score = min(max(surge - 0.8, 0.0) / 1.2, 1.0)

    raw = (
        0.28 * volatility_fit
        + 0.22 * rsi_fit
        + 0.20 * not_extended
        + 0.18 * min(momentum / 1.75, 1.0)
        + 0.12 * volume_score
    )

    predicted_gain = config.MIN_GAIN_PCT + raw * (
        config.MAX_GAIN_PCT - config.MIN_GAIN_PCT
    )
    if vol < 40:
        predicted_gain = min(predicted_gain, 15.0)
    if vol > 120:
        predicted_gain = min(max(predicted_gain, 18.0), config.MAX_GAIN_PCT)

    confidence = round(min(0.35 + raw * 0.55, 0.90), 2)
    predicted_gain = round(predicted_gain, 1)
    levels = _trade_levels(price, predicted_gain, close, vol)
    target = float(levels["tp2_usd"])
    near_low = bool(levels["near_low"])

    prob_overall, prob_tp1, prob_tp2 = _probability_pcts(
        raw_score=raw,
        rsi=rsi,
        surge=surge,
        bounce=bounce,
        rr1=float(levels["risk_reward_tp1"]),
        predicted_gain_pct=predicted_gain,
    )
    best_time, best_reason = _best_trade_time(
        entry_note=str(levels["entry_note"]),
        near_low=near_low,
        vol_ann_pct=vol,
        volume_24h=volume_24h,
    )

    reasons: list[str] = []
    if surge >= 1.25:
        reasons.append("rising volume")
    if 35 <= rsi <= 55:
        reasons.append(f"RSI {rsi:.0f} with room to run")
    elif rsi < 35:
        reasons.append(f"oversold RSI {rsi:.0f}")
    if change_24h > 1:
        reasons.append(f"+{change_24h:.1f}% / 24h momentum")
    if bounce < 12:
        reasons.append("near recent range low")
    if 50 <= vol <= 120:
        reasons.append(f"tradeable volatility (~{vol:.0f}% ann.)")
    if not reasons:
        reasons.append("balanced technical setup vs peers")

    return Prediction(
        rank=0,
        symbol=str(market.get("symbol", "")).upper(),
        name=str(market.get("name", "")),
        coin_id=str(market.get("id", "")),
        price_usd=_round_price(price),
        predicted_gain_pct=predicted_gain,
        target_price_usd=target,
        entry_usd=float(levels["entry_usd"]),
        tp1_usd=float(levels["tp1_usd"]),
        tp2_usd=float(levels["tp2_usd"]),
        sl_usd=float(levels["sl_usd"]),
        entry_note=str(levels["entry_note"]),
        risk_reward_tp1=float(levels["risk_reward_tp1"]),
        risk_reward_tp2=float(levels["risk_reward_tp2"]),
        probability_pct=prob_overall,
        probability_tp1_pct=prob_tp1,
        probability_tp2_pct=prob_tp2,
        best_time_sast=best_time,
        best_time_reason=best_reason,
        confidence=confidence,
        score=round(raw, 4),
        reason="; ".join(reasons),
        volume_24h_usd=round(volume_24h, 2),
        change_24h_pct=round(change_24h, 2),
        change_7d_pct=round(change_7d, 2),
        rsi_14=round(rsi, 1),
        volatility_14d_pct=round(vol, 1),
    )


def rank_predictions(candidates: list[Prediction], top_n: int = 5) -> list[Prediction]:
    ordered = sorted(candidates, key=lambda p: p.score, reverse=True)[:top_n]
    for i, pred in enumerate(ordered, start=1):
        pred.rank = i
    return ordered
