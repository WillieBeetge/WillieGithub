"""Score coins for plausible short-term 10–30% upside setups."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

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

    # Prefer coins that can realistically move 10–30%: enough volatility,
    # not already extended, with constructive short-term momentum / volume.
    volatility_fit = 1.0 - min(abs(vol - 80.0) / 80.0, 1.0)  # sweet spot ~ mid/high vol
    rsi_fit = 1.0 - min(abs(rsi - 45.0) / 45.0, 1.0)  # prefer mid RSI, room to run
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

    # Map score into a predicted gain inside the requested 10–30% band.
    predicted_gain = config.MIN_GAIN_PCT + raw * (
        config.MAX_GAIN_PCT - config.MIN_GAIN_PCT
    )
    # Soften extreme volatility into the upper band, dampen dead coins.
    if vol < 40:
        predicted_gain = min(predicted_gain, 15.0)
    if vol > 120:
        predicted_gain = min(max(predicted_gain, 18.0), config.MAX_GAIN_PCT)

    confidence = round(min(0.35 + raw * 0.55, 0.90), 2)
    target = price * (1 + predicted_gain / 100.0)

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
        price_usd=round(price, 8 if price < 1 else 4),
        predicted_gain_pct=round(predicted_gain, 1),
        target_price_usd=round(target, 8 if target < 1 else 4),
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
