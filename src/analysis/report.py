"""
Report generator: prints summary table, saves equity curve PNG and trade log CSV.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.backtest.metrics import compute_metrics, print_metrics
from src.backtest.portfolio import Portfolio

OUTPUT_DIR = Path("/Users/ashwanthkumar/trading/learn-trading-from-x/output")


def generate_report(
    portfolio: Portfolio,
    strategy_name: str,
    start_date: date,
    end_date: date,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    equity_df = portfolio.equity_df()
    trade_df = portfolio.trade_log_df()

    # Compute and print metrics
    metrics = compute_metrics(equity_df, trade_df)
    print_metrics(metrics)

    # Save trade log CSV
    tag = f"{strategy_name}_{start_date}_{end_date}"
    if not trade_df.empty:
        trade_path = OUTPUT_DIR / f"trade_log_{tag}.csv"
        trade_df.to_csv(trade_path, index=False)
        print(f"\nTrade log saved: {trade_path}")

    # Save equity curve PNG
    if not equity_df.empty:
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        # Equity curve
        axes[0].plot(equity_df.index, equity_df["equity"], linewidth=1.5, color="steelblue")
        axes[0].axhline(portfolio.initial_cash, color="gray", linestyle="--", alpha=0.5, label="Initial capital")
        axes[0].set_ylabel("Portfolio Value (₹)")
        axes[0].set_title(f"Equity Curve — {strategy_name} ({start_date} to {end_date})")
        axes[0].legend()
        axes[0].grid(alpha=0.3)

        # Drawdown
        rolling_max = equity_df["equity"].cummax()
        drawdown = (equity_df["equity"] - rolling_max) / rolling_max * 100
        axes[1].fill_between(equity_df.index, drawdown, 0, color="red", alpha=0.4)
        axes[1].set_ylabel("Drawdown (%)")
        axes[1].set_xlabel("Date")
        axes[1].grid(alpha=0.3)

        plt.tight_layout()
        chart_path = OUTPUT_DIR / f"equity_curve_{tag}.png"
        plt.savefig(chart_path, dpi=150)
        plt.close()
        print(f"Equity curve saved: {chart_path}")

    # Print brief trade summary
    if not trade_df.empty and "pnl" in trade_df.columns:
        closed = trade_df.dropna(subset=["pnl"])
        print(f"\nClosed trades: {len(closed)}")
        if not closed.empty:
            print(f"  Winners: {(closed['pnl'] > 0).sum()}")
            print(f"  Losers:  {(closed['pnl'] <= 0).sum()}")
            print(f"  Best P&L:  ₹{closed['pnl'].max():,.0f}")
            print(f"  Worst P&L: ₹{closed['pnl'].min():,.0f}")
