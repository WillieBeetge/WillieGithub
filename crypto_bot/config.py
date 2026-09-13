"""Configuration for the SA crypto prediction bot."""

from pathlib import Path

# South African Standard Time (UTC+2, no DST)
TIMEZONE = "Africa/Johannesburg"
RUN_HOURS = (6, 16)  # 06:00 and 16:00 SAST

# How many coins to recommend each run
TOP_N = 5

# Target gain band used when ranking candidates
MIN_GAIN_PCT = 10.0
MAX_GAIN_PCT = 30.0

# Universe: liquid, tradeable alts (exclude stables / wrapped duplicates)
# CoinGecko IDs — widely listed on major exchanges
CANDIDATE_IDS = [
    "bitcoin",
    "ethereum",
    "solana",
    "binancecoin",
    "ripple",
    "cardano",
    "dogecoin",
    "avalanche-2",
    "polkadot",
    "chainlink",
    "polygon-ecosystem-token",
    "litecoin",
    "uniswap",
    "near",
    "cosmos",
    "aptos",
    "sui",
    "arbitrum",
    "optimism",
    "render-token",
    "injective-protocol",
    "fetch-ai",
    "filecoin",
    "hedera-hashgraph",
    "stellar",
    "tron",
    "toncoin",
    "kaspa",
    "pepe",
    "shiba-inu",
]

# Prefer coins with enough volume to actually trade
MIN_24H_VOLUME_USD = 5_000_000

# Output
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "predictions"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# CoinGecko (no API key required for public endpoints; be polite with rate limits)
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT_SEC = 30
REQUEST_PAUSE_SEC = 2.0
