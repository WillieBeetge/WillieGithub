"""Run one full prediction cycle."""

from __future__ import annotations

import logging

from crypto_bot import config
from crypto_bot.analyzer import Prediction, rank_predictions, score_coin
from crypto_bot.data_fetcher import CoinGeckoClient
from crypto_bot.reporter import print_report, save_report

logger = logging.getLogger(__name__)


def _prefilter_ids(markets: list[dict]) -> list[str]:
    """Pick the most promising liquid names before chart fetches (rate-limit friendly)."""
    eligible: list[tuple[float, str]] = []
    for m in markets:
        vol = float(m.get("total_volume") or 0)
        price = float(m.get("current_price") or 0)
        if vol < config.MIN_24H_VOLUME_USD or price <= 0:
            continue
        change_24h = float(m.get("price_change_percentage_24h") or 0)
        change_7d = float(m.get("price_change_percentage_7d_in_currency") or 0)
        priority = vol + max(change_24h, 0) * 1e6 - max(change_7d - 40, 0) * 5e6
        eligible.append((priority, m["id"]))
    eligible.sort(reverse=True)
    return [coin_id for _, coin_id in eligible[:12]]


def run_once(print_output: bool = True) -> list[Prediction]:
    client = CoinGeckoClient()
    logger.info("Fetching market data for %d candidates…", len(config.CANDIDATE_IDS))
    markets = client.markets(config.CANDIDATE_IDS)
    by_id = {m["id"]: m for m in markets if "id" in m}
    shortlist = _prefilter_ids(markets)
    logger.info("Deep-scoring shortlist of %d coins…", len(shortlist))

    scored: list[Prediction] = []
    for coin_id in shortlist:
        market = by_id.get(coin_id)
        if not market:
            logger.debug("Missing market row for %s", coin_id)
            continue
        try:
            chart = client.market_chart(coin_id, days=30)
            pred = score_coin(market, chart)
            if pred:
                scored.append(pred)
                logger.info(
                    "Scored %s: gain≈%.1f%% prob≈%.0f%% score=%.3f",
                    pred.symbol,
                    pred.predicted_gain_pct,
                    pred.probability_pct,
                    pred.score,
                )
        except Exception:
            logger.exception("Failed scoring %s", coin_id)

    top = rank_predictions(scored, top_n=config.TOP_N)
    if not top:
        raise RuntimeError(
            "No tradeable setups found. Check network access or relax filters."
        )

    path = save_report(top)
    logger.info("Saved report to %s", path)
    if print_output:
        print_report(top)
    return top
