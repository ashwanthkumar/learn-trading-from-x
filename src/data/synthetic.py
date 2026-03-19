"""
Synthetic spot and ATM strike derivation via put-call parity.

For a given option chain snapshot:
  F = K + CE_close - PE_close   (synthetic future)
  ATM strike = argmin |CE_close - PE_close|
"""

from __future__ import annotations


def find_atm(chain: dict[int, dict[str, dict]]) -> tuple[int, float] | tuple[None, None]:
    """
    Scan chain for the strike where |CE_close - PE_close| is minimised.

    Returns (atm_strike, synthetic_future_price) or (None, None) if insufficient data.
    """
    best_strike = None
    best_diff = float("inf")
    best_future = None

    for strike, bars in chain.items():
        ce = bars.get("CE")
        pe = bars.get("PE")
        if ce is None or pe is None:
            continue
        ce_close = ce.get("close")
        pe_close = pe.get("close")
        if ce_close is None or pe_close is None:
            continue
        if ce_close <= 0 or pe_close <= 0:
            continue

        diff = abs(ce_close - pe_close)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike
            best_future = strike + ce_close - pe_close

    return best_strike, best_future


def get_straddle_premium(chain: dict[int, dict[str, dict]], strike: int) -> float | None:
    """Return CE_close + PE_close for the given strike, or None if unavailable."""
    bars = chain.get(strike)
    if not bars:
        return None
    ce = bars.get("CE")
    pe = bars.get("PE")
    if ce is None or pe is None:
        return None
    ce_close = ce.get("close")
    pe_close = pe.get("close")
    if ce_close is None or pe_close is None:
        return None
    return ce_close + pe_close


def straddle_as_pct_of_spot(straddle_premium: float, spot: float) -> float:
    """Return straddle premium as a fraction of spot price."""
    if spot <= 0:
        return 0.0
    return straddle_premium / spot


def round_to_strike_interval(price: float, interval: int = 50) -> int:
    """Round a price to the nearest strike interval."""
    return round(price / interval) * interval
