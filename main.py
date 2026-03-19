"""
CLI entry point for the Sarang Sood strategy backtester.

Usage:
  uv run main.py --from 2024-01 --to 2024-03 --strategy long_straddle
  uv run main.py --from 2024-01 --to 2024-03 --strategy debit_spread
  uv run main.py --from 2024-01 --to 2024-03 --strategy both
"""

import argparse
import sys
from datetime import date


def parse_ym(s: str) -> date:
    """Parse 'YYYY-MM' into the first day of that month."""
    parts = s.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Expected YYYY-MM, got: {s!r}")
    return date(int(parts[0]), int(parts[1]), 1)


def last_day_of_month(d: date) -> date:
    """Return the last day of the given month."""
    import calendar
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest Sarang Sood Nifty options strategies"
    )
    parser.add_argument(
        "--from", dest="start", required=True, type=parse_ym,
        metavar="YYYY-MM", help="Start month (inclusive)"
    )
    parser.add_argument(
        "--to", dest="end", required=True, type=parse_ym,
        metavar="YYYY-MM", help="End month (inclusive)"
    )
    parser.add_argument(
        "--strategy",
        choices=["long_straddle", "debit_spread", "both"],
        default="long_straddle",
        help="Strategy to run (default: long_straddle)",
    )
    parser.add_argument(
        "--lots", type=int, default=1,
        help="Number of lots per trade (default: 1)"
    )
    parser.add_argument(
        "--capital", type=float, default=1_000_000.0,
        help="Initial capital in rupees (default: 10 lakh)"
    )
    parser.add_argument(
        "--iv-threshold", type=float, default=0.025,
        help="Straddle-as-pct-of-spot threshold for high-IV regime (default: 0.025 = 2.5%%)"
    )
    parser.add_argument(
        "--intraday", action="store_true",
        help="Intraday mode: enter any day ≤09:30, exit at 15:15 (default: positional Mon–Thu)"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-bar verbose output"
    )

    args = parser.parse_args()
    start_date = args.start
    end_date = last_day_of_month(args.end)

    if start_date > end_date:
        print("Error: --from must be before --to", file=sys.stderr)
        sys.exit(1)

    mode = "intraday" if args.intraday else "positional"
    print(f"Backtest: {start_date} → {end_date}")
    print(f"Strategy: {args.strategy} | Mode: {mode} | Lots: {args.lots} | Capital: ₹{args.capital:,.0f}")
    print(f"IV threshold: {args.iv_threshold*100:.1f}%")
    print()

    from src.backtest.engine import BacktestEngine
    from src.analysis.report import generate_report

    strategies_to_run = (
        ["long_straddle", "debit_spread"] if args.strategy == "both"
        else [args.strategy]
    )

    for strat_name in strategies_to_run:
        print(f"\n{'='*60}")
        print(f"  Running: {strat_name}")
        print(f"{'='*60}")

        if strat_name == "long_straddle":
            from src.strategies.long_straddle import LongStraddleStrategy
            strategy = LongStraddleStrategy(
                lots=args.lots,
                high_iv_threshold=args.iv_threshold,
                intraday=args.intraday,
            )
        else:
            from src.strategies.debit_spread import DebitSpreadStrategy
            strategy = DebitSpreadStrategy(
                lots=args.lots,
                high_iv_threshold=args.iv_threshold,
                intraday=args.intraday,
            )

        engine = BacktestEngine(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_cash=args.capital,
            verbose=not args.quiet,
        )

        portfolio = engine.run()
        generate_report(portfolio, strat_name, start_date, end_date, intraday=args.intraday)


if __name__ == "__main__":
    main()
