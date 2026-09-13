# WillieGithub — SA Crypto Prediction Bot

Python bot that screens liquid cryptocurrencies and prints **5 tradeable setups** with a modelled **10–30% upside** band. Runs on demand, or on a schedule at **06:00 and 16:00 Africa/Johannesburg (SAST)**.

> **Not financial advice.** These are heuristic technical screens, not guarantees. Crypto is volatile — do your own research and never risk money you cannot afford to lose.

## Features

- Pulls live market + 30-day history from [CoinGecko](https://www.coingecko.com/) (no API key required for public endpoints)
- Scores coins on volatility fit, RSI room-to-run, volume surge, and short-term momentum
- Filters for tradeable liquidity (default min ~$5M 24h volume)
- Saves JSON + text reports under `predictions/`
- Cron-style scheduler for **06:00** and **16:00 SAST**

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run one cycle now:

```bash
python -m crypto_bot --once
```

Keep the process alive and run at **06:00** and **16:00** South African time (also runs once on start):

```bash
python -m crypto_bot --schedule
```

Verbose logs:

```bash
python -m crypto_bot --once -v
```

## Output

Each run writes:

- `predictions/predictions_YYYYMMDD_HHMMSS.json`
- `predictions/predictions_YYYYMMDD_HHMMSS.txt`
- `predictions/latest.json` and `predictions/latest.txt` (always the newest)

Example fields per coin: symbol, spot price, **Entry / TP1 / TP2 / SL**, risk:reward, predicted gain %, confidence, RSI, volatility, and a short reason.

Trade levels (long bias):
- **Entry** — market if near recent low, otherwise a small limit pullback
- **TP1** — first take-profit (~45% of modelled move)
- **TP2** — full modelled target (10–30% band)
- **SL** — stop under recent structure / volatility buffer

## How scoring works

For each candidate in a curated liquid universe, the bot:

1. Rejects low-volume coins  
2. Computes RSI(14), realized volatility, distance from recent low, and volume surge  
3. Maps a composite score into a **10–30%** predicted-gain band  
4. Ranks and returns the **top 5**

This is a rules-based screen, not ML price prophecy.

## Deploy tip (always-on)

On a VPS or home server:

```bash
# example systemd unit idea — adjust paths/user
python -m crypto_bot --schedule
```

Or call `python -m crypto_bot --once` from system cron at 04:00 and 14:00 UTC (equivalent to 06:00 / 16:00 SAST).

## Config

Edit `crypto_bot/config.py` to change candidate coins, volume floor, gain band, or schedule hours.
