"""
Option chain builder: loads 1-min bars for a given date and expiry.
"""

from __future__ import annotations

import io
from datetime import date, time
from pathlib import Path

import pandas as pd

_CSV_COLS = ["ticker", "date", "time", "open", "high", "low", "close", "volume", "oi"]
_CACHE: dict[Path, pd.DataFrame] = {}


def _load_csv(path: Path) -> pd.DataFrame:
    """Load a single option CSV; result is cached in memory."""
    if path in _CACHE:
        return _CACHE[path]

    df = pd.read_csv(
        path,
        header=0,
        names=_CSV_COLS,
        parse_dates=False,
    )
    df.columns = _CSV_COLS
    # Parse date (MM/DD/YYYY) and time (HH:MM:SS)
    df["dt"] = pd.to_datetime(
        df["date"].str.strip() + " " + df["time"].str.strip(),
        format="%m/%d/%Y %H:%M:%S",
    )
    df = df.drop(columns=["date", "time"])
    df = df.set_index("dt").sort_index()
    _CACHE[path] = df
    return df


def load_bar(csv_path: Path, bar_dt: pd.Timestamp) -> dict | None:
    """
    Return the OHLCV+OI row closest to bar_dt (within same minute), or None.
    """
    df = _load_csv(csv_path)
    # Match by minute-level truncation
    minute_key = bar_dt.floor("min")
    if minute_key in df.index:
        row = df.loc[minute_key]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        return row.to_dict()
    return None


def get_bars_for_date(csv_path: Path, trade_date: date) -> pd.DataFrame:
    """Return all 1-min bars for a specific calendar date."""
    df = _load_csv(csv_path)
    mask = df.index.date == trade_date
    return df[mask]


def build_chain(
    index: dict,
    trade_date: date,
    expiry_key: str,
    bar_time: time | None = None,
) -> dict[int, dict[str, dict]]:
    """
    Build option chain snapshot for a given date and expiry.

    Returns:
        { strike: { 'CE': bar_dict_or_None, 'PE': bar_dict_or_None } }

    If bar_time is None, returns the last bar of the day for each strike.
    """
    strikes_data = index.get(expiry_key, {})
    chain: dict[int, dict[str, dict]] = {}

    if bar_time is not None:
        bar_dt = pd.Timestamp(
            year=trade_date.year,
            month=trade_date.month,
            day=trade_date.day,
            hour=bar_time.hour,
            minute=bar_time.minute,
            second=0,
        )

    for strike, type_paths in strikes_data.items():
        ce_bar = pe_bar = None

        for opt_type in ("CE", "PE"):
            path = type_paths.get(opt_type)
            if path is None:
                continue
            try:
                if bar_time is not None:
                    bar = load_bar(path, bar_dt)
                else:
                    day_df = get_bars_for_date(path, trade_date)
                    bar = day_df.iloc[-1].to_dict() if not day_df.empty else None
            except Exception:
                bar = None

            if opt_type == "CE":
                ce_bar = bar
            else:
                pe_bar = bar

        if ce_bar is not None or pe_bar is not None:
            chain[strike] = {"CE": ce_bar, "PE": pe_bar}

    return chain


def clear_cache() -> None:
    """Free in-memory CSV cache (call between months to limit RAM usage)."""
    _CACHE.clear()
