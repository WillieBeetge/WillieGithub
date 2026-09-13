#!/usr/bin/env python3
"""SA Crypto Prediction Bot — CLI entrypoint.

Screens liquid cryptocurrencies and prints the top 5 setups with a modelled
10–30% upside band, Entry/TP1/TP2/SL, probability %, and best SAST trade time.
Can run once or on a schedule at 06:00 and 16:00 Africa/Johannesburg.
"""

from __future__ import annotations

import argparse
import logging
import sys

from crypto_bot.pipeline import run_once
from crypto_bot.scheduler import start_scheduler


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Predict top 5 tradeable cryptos with a possible 10–30% gain, "
            "probability %, and best SAST trade time. "
            "Schedule: 06:00 and 16:00 South African time."
        )
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single prediction cycle now and exit",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Keep running and fire at 06:00 and 16:00 Africa/Johannesburg",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    args = parser.parse_args(argv)

    if not args.once and not args.schedule:
        args.once = True

    _configure_logging(args.verbose)

    try:
        if args.schedule:
            logging.getLogger(__name__).info(
                "Running an initial cycle, then waiting for schedule…"
            )
            run_once(print_output=True)
            start_scheduler()
        else:
            run_once(print_output=True)
    except Exception as exc:
        logging.getLogger(__name__).error("Bot failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
