"""
Backtest engine: iterates over trading days and bars, calls strategy on each bar.

Design:
- For each month in the date range, extract & index the RAR.
- For each trading day, build the EOD chain (last bar of day per strike).
- Call strategy.on_bar() → collect orders → execute at market (same bar price).
- Record EOD equity.
"""

from __future__ import annotations

import sys
from datetime import date, time

from src.data.chain import build_chain, clear_cache
from src.data.loader import extract_month, index_nifty_files
from src.data.synthetic import find_atm
from src.strategies.base import Strategy, StrategyState
from src.backtest.portfolio import Portfolio

# Indian market session
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
# Bar we use for strategy decisions (end of day signal)
EOD_BAR = time(15, 25)


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        start_date: date,
        end_date: date,
        initial_cash: float = 1_000_000.0,
        verbose: bool = True,
    ):
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.portfolio = Portfolio(initial_cash)
        self.verbose = verbose
        self._state = StrategyState()

    def run(self) -> Portfolio:
        """Run the backtest; return portfolio with full trade log and equity curve."""
        # Generate (year, month) pairs to process
        months = self._months_in_range()

        for year, month in months:
            self._process_month(year, month)
            clear_cache()  # Free RAM between months

        return self.portfolio

    def _months_in_range(self) -> list[tuple[int, int]]:
        result = []
        y, m = self.start_date.year, self.start_date.month
        while (y, m) <= (self.end_date.year, self.end_date.month):
            result.append((y, m))
            m += 1
            if m > 12:
                m = 1
                y += 1
        return result

    def _process_month(self, year: int, month: int) -> None:
        if self.verbose:
            print(f"Processing {year}-{month:02d}...", flush=True)

        try:
            extract_month(year, month)
            index = index_nifty_files(year, month)
        except FileNotFoundError as e:
            print(f"  Skipping: {e}", file=sys.stderr)
            return
        except RuntimeError as e:
            print(f"  Error extracting: {e}", file=sys.stderr)
            return

        if not index:
            print(f"  No NIFTY files found for {year}-{month:02d}")
            return

        # Get all trading days for this month that fall in [start_date, end_date]
        trading_days = self._get_trading_days(index, year, month)

        for trade_date in trading_days:
            self._process_day(index, trade_date)

    def _get_trading_days(self, index: dict, year: int, month: int) -> list[date]:
        """
        Return all weekdays in (year, month) that fall within the backtest range.
        The engine will naturally skip days with no chain data.
        """
        import calendar
        _, last_day = calendar.monthrange(year, month)
        days = []
        for day in range(1, last_day + 1):
            d = date(year, month, day)
            if d.weekday() < 5 and self.start_date <= d <= self.end_date:
                days.append(d)
        return days

    def _process_day(self, index: dict, trade_date: date) -> None:
        """Process all bars for a single trading day."""
        # Select nearest expiry on or after trade_date
        expiry_key = self.strategy.select_nearest_expiry(index, trade_date)
        if expiry_key is None:
            return

        # Build EOD chain
        chain = build_chain(index, trade_date, expiry_key, bar_time=EOD_BAR)
        if not chain:
            return

        # Call strategy
        orders = self.strategy.on_bar(
            chain=chain,
            trade_date=trade_date,
            bar_time=EOD_BAR,
            expiry_key=expiry_key,
            state=self._state,
            portfolio=self.portfolio,
        )

        # Execute orders
        for order in orders:
            # Use the provided price (same-bar execution; no next-bar slippage in EOD mode)
            self.portfolio.execute(order)

        # Record EOD equity
        self.portfolio.record_eod(trade_date, chain)

        if self.verbose:
            eq = self.portfolio.equity_curve[-1]["equity"]
            print(
                f"  {trade_date} | expiry={expiry_key} | "
                f"orders={len(orders)} | equity={eq:,.0f}",
                flush=True,
            )
