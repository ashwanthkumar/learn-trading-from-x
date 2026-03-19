"""
Backtest engine: iterates over every 1-minute bar of every trading day,
calling the strategy on each bar.

Design:
- For each month in the date range, extract & index the RAR.
- For each trading day, enumerate all 1-minute timestamps that appear in the data.
- For each bar, build the option chain snapshot and call strategy.on_bar().
- Orders execute at the bar 2 bars later (t+2 slippage to simulate live latency).
- Record EOD equity after the last bar of each day.
"""

from __future__ import annotations

import calendar
import sys
from datetime import date, time

import pandas as pd

from src.data.chain import build_chain, clear_cache, _load_csv
from src.data.loader import extract_month, index_nifty_files
from src.strategies.base import Strategy, StrategyState
from src.backtest.portfolio import Portfolio

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


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
        # t+2 fill queue: list of (bars_remaining, [orders])
        self._order_queue: list[tuple[int, list]] = []

    def run(self) -> Portfolio:
        months = self._months_in_range()
        for year, month in months:
            self._process_month(year, month)
            clear_cache()
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

        trading_days = self._get_trading_days(year, month)
        for trade_date in trading_days:
            self._process_day(index, trade_date)

    def _get_trading_days(self, year: int, month: int) -> list[date]:
        _, last_day = calendar.monthrange(year, month)
        return [
            date(year, month, day)
            for day in range(1, last_day + 1)
            if date(year, month, day).weekday() < 5
            and self.start_date <= date(year, month, day) <= self.end_date
        ]

    def _get_bar_timestamps(self, index: dict, trade_date: date, expiry_key: str) -> list[pd.Timestamp]:
        """
        Enumerate all 1-minute timestamps for this date by reading a handful
        of liquid strike CSVs and taking the union of their timestamps.
        """
        strikes_data = index.get(expiry_key, {})
        timestamps: set[pd.Timestamp] = set()
        files_checked = 0

        for strike_data in strikes_data.values():
            path = strike_data.get("PE") or strike_data.get("CE")
            if path is None or not path.exists():
                continue
            try:
                df = _load_csv(path)
                day_mask = df.index.date == trade_date
                timestamps.update(df.index[day_mask])
                files_checked += 1
            except Exception:
                continue
            if files_checked >= 5:  # 5 files gives good timestamp coverage
                break

        return sorted(timestamps)

    def _process_day(self, index: dict, trade_date: date) -> None:
        expiry_key = self.strategy.select_nearest_expiry(index, trade_date)
        if expiry_key is None:
            return

        bar_timestamps = self._get_bar_timestamps(index, trade_date, expiry_key)
        if not bar_timestamps:
            return

        last_chain = None

        for ts in bar_timestamps:
            bar_time = ts.time()

            # Build chain for this bar
            chain = build_chain(index, trade_date, expiry_key, bar_time=bar_time)
            if not chain:
                continue

            # Tick down the t+2 queue and fill orders whose countdown reached 0
            still_pending = []
            for bars_left, orders in self._order_queue:
                bars_left -= 1
                if bars_left <= 0:
                    for order in orders:
                        # Fill at this bar's open price
                        if order.opt_type != "FUT":
                            bar = chain.get(order.strike, {}).get(order.opt_type)
                            if bar is not None:
                                order.price = bar.get("open", order.price)
                        self.portfolio.execute(order)
                else:
                    still_pending.append((bars_left, orders))
            self._order_queue = still_pending

            # Call strategy — returns orders to enqueue with t+2 countdown
            new_orders = self.strategy.on_bar(
                chain=chain,
                trade_date=trade_date,
                bar_time=bar_time,
                expiry_key=expiry_key,
                state=self._state,
                portfolio=self.portfolio,
            )
            if new_orders:
                self._order_queue.append((2, new_orders))

            last_chain = chain

        # Flush any unfilled orders at EOD close (can't carry across days for options)
        if self._order_queue and last_chain:
            for _, orders in self._order_queue:
                for order in orders:
                    if order.opt_type != "FUT":
                        bar = last_chain.get(order.strike, {}).get(order.opt_type)
                        if bar is not None:
                            order.price = bar.get("close", order.price)
                    self.portfolio.execute(order)
            self._order_queue = []

        # Record EOD equity using the last available chain
        if last_chain:
            self.portfolio.record_eod(trade_date, last_chain)

        if self.verbose and last_chain:
            eq = self.portfolio.equity_curve[-1]["equity"]
            n_bars = len(bar_timestamps)
            print(
                f"  {trade_date} | expiry={expiry_key} | bars={n_bars} | equity={eq:,.0f}",
                flush=True,
            )
