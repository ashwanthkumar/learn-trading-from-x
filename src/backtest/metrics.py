"""
Performance metrics: Sharpe, max drawdown, win rate, CAGR, avg hold time.
"""

from __future__ import annotations

import math

import pandas as pd


def compute_metrics(equity_df: pd.DataFrame, trade_log_df: pd.DataFrame) -> dict:
    """
    Compute standard performance metrics.

    Args:
        equity_df: indexed by date, must have 'equity' column
        trade_log_df: trade log with optional 'pnl', 'hold_days' columns

    Returns:
        dict of metric name → value
    """
    metrics: dict = {}

    if equity_df.empty:
        return {"error": "No equity data"}

    equity = equity_df["equity"]
    initial = equity.iloc[0]
    final = equity.iloc[-1]

    # Total return
    metrics["total_return_pct"] = (final / initial - 1) * 100

    # CAGR
    n_days = (equity.index[-1] - equity.index[0]).days
    n_years = n_days / 365.25
    if n_years > 0 and initial > 0:
        metrics["cagr_pct"] = ((final / initial) ** (1 / n_years) - 1) * 100
    else:
        metrics["cagr_pct"] = 0.0

    # Daily returns
    daily_returns = equity.pct_change().dropna()

    # Sharpe ratio (annualised, 0% risk-free)
    if daily_returns.std() > 0:
        metrics["sharpe"] = (daily_returns.mean() / daily_returns.std()) * math.sqrt(252)
    else:
        metrics["sharpe"] = 0.0

    # Max drawdown
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    metrics["max_drawdown_pct"] = drawdown.min() * 100

    # Trade-level metrics
    if not trade_log_df.empty and "pnl" in trade_log_df.columns:
        closed = trade_log_df.dropna(subset=["pnl"])
        if not closed.empty:
            metrics["total_trades"] = len(closed)
            metrics["win_rate_pct"] = (closed["pnl"] > 0).mean() * 100
            metrics["avg_pnl"] = closed["pnl"].mean()
            metrics["total_pnl"] = closed["pnl"].sum()
            if "hold_days" in closed.columns:
                metrics["avg_hold_days"] = closed["hold_days"].mean()
        else:
            metrics["total_trades"] = 0
    else:
        metrics["total_trades"] = 0

    return metrics


def print_metrics(metrics: dict) -> None:
    print("\n" + "=" * 50)
    print("  BACKTEST PERFORMANCE SUMMARY")
    print("=" * 50)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<25} {v:>12.2f}")
        else:
            print(f"  {k:<25} {v!r:>12}")
    print("=" * 50)
