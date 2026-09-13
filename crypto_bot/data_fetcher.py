"""Fetch market and OHLC data from CoinGecko."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from crypto_bot import config

logger = logging.getLogger(__name__)


class CoinGeckoClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "sa-crypto-prediction-bot/1.0",
            }
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{config.COINGECKO_BASE}{path}"
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                resp = self.session.get(
                    url, params=params, timeout=config.REQUEST_TIMEOUT_SEC
                )
                if resp.status_code == 429:
                    wait = 15 * (attempt + 1)
                    logger.warning("Rate limited by CoinGecko; sleeping %ss", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                time.sleep(config.REQUEST_PAUSE_SEC)
                return resp.json()
            except requests.RequestException as exc:
                last_error = exc
                wait = 5 * (attempt + 1)
                logger.warning("Request failed (%s); retry in %ss", exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"CoinGecko request failed after retries: {last_error}")

    def markets(self, ids: list[str]) -> list[dict[str, Any]]:
        """Current market snapshot for the candidate universe."""
        params = {
            "vs_currency": "usd",
            "ids": ",".join(ids),
            "order": "market_cap_desc",
            "per_page": len(ids),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d,14d,30d",
        }
        data = self._get("/coins/markets", params)
        return data if isinstance(data, list) else []

    def market_chart(self, coin_id: str, days: int = 30) -> dict[str, Any]:
        """Daily-ish price/volume history for technical scoring."""
        params = {
            "vs_currency": "usd",
            "days": days,
            "interval": "daily",
        }
        data = self._get(f"/coins/{coin_id}/market_chart", params)
        return data if isinstance(data, dict) else {}
