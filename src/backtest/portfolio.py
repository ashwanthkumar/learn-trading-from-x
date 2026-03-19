"""
Portfolio: tracks positions (options + futures), cash, and MTM P&L.

Lot sizes:
  - Pre-Oct 2024: 50 units per lot
  - Oct 2024 onwards: 75 units per lot
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

from src.strategies.base import Order


def lot_size(trade_date: date) -> int:
    """Return Nifty lot size for the given trade date."""
    cutoff = date(2024, 10, 1)
    return 75 if trade_date >= cutoff else 50


@dataclass
class Position:
    symbol: str
    expiry_key: str
    strike: int
    opt_type: str           # CE, PE, or FUT
    action: Literal["BUY", "SELL"]
    qty_lots: int
    entry_price: float
    entry_date: date
    units: int              # qty_lots * lot_size


class Portfolio:
    def __init__(self, initial_cash: float = 1_000_000.0):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: list[Position] = []
        self.trade_log: list[dict] = []
        self.equity_curve: list[dict] = []

    def execute(self, order: Order) -> None:
        """Execute an order: update cash and position book."""
        units = order.qty * lot_size(order.trade_date)
        price = order.price

        if order.opt_type == "FUT":
            self._execute_futures(order, units, price)
        elif order.action == "BUY":
            self._open_long(order, units, price)
        elif order.action == "SELL":
            # Try to close an existing long first; otherwise open a short
            matched = self._find_position(order.symbol, order.strike, order.opt_type, "BUY")
            if matched:
                self._close_long(order, matched, units, price)
            else:
                self._open_short(order, units, price)

    def _open_long(self, order: Order, units: int, price: float) -> None:
        cost = price * units
        self.cash -= cost
        self.positions.append(Position(
            symbol=order.symbol, expiry_key=order.expiry_key,
            strike=order.strike, opt_type=order.opt_type,
            action="BUY", qty_lots=order.qty,
            entry_price=price, entry_date=order.trade_date, units=units,
        ))
        self.trade_log.append({
            "date": order.trade_date, "time": order.trade_time,
            "symbol": order.symbol, "action": "BUY",
            "price": price, "units": units, "cash_flow": -cost, "tag": order.tag,
        })

    def _close_long(self, order: Order, matched: Position, units: int, price: float) -> None:
        proceeds = price * units
        self.cash += proceeds
        pnl = (price - matched.entry_price) * units
        self.positions.remove(matched)
        self.trade_log.append({
            "date": order.trade_date, "time": order.trade_time,
            "symbol": order.symbol, "action": "SELL",
            "price": price, "units": units, "cash_flow": proceeds,
            "pnl": pnl, "entry_price": matched.entry_price,
            "entry_date": matched.entry_date,
            "hold_days": (order.trade_date - matched.entry_date).days,
            "tag": order.tag,
        })

    def _open_short(self, order: Order, units: int, price: float) -> None:
        """Open a short option position (for debit spread sold legs)."""
        self.cash += price * units  # receive premium
        self.positions.append(Position(
            symbol=order.symbol, expiry_key=order.expiry_key,
            strike=order.strike, opt_type=order.opt_type,
            action="SELL", qty_lots=order.qty,
            entry_price=price, entry_date=order.trade_date, units=units,
        ))
        self.trade_log.append({
            "date": order.trade_date, "time": order.trade_time,
            "symbol": order.symbol, "action": "SELL_OPEN",
            "price": price, "units": units, "cash_flow": price * units, "tag": order.tag,
        })

    def _execute_futures(self, order: Order, units: int, price: float) -> None:
        """
        Execute a delta-hedge futures trade.
        BUY futures: net long delta offset (spot fell, we're net short delta).
        SELL futures: net short delta offset (spot rose, we're net long delta).
        Futures require no cash outlay (margin not modelled); P&L is mark-to-market.
        We store futures positions and mark them vs current synthetic spot.
        """
        # Look for an offsetting futures position to close (netting)
        reverse_action = "SELL" if order.action == "BUY" else "BUY"
        matched = self._find_position(order.symbol, order.strike, order.opt_type, reverse_action)

        if matched:
            # Close (fully or partially) an existing futures leg
            pnl = ((price - matched.entry_price) * units
                   if reverse_action == "BUY"   # we were long, now selling
                   else (matched.entry_price - price) * units)  # we were short, now buying
            self.cash += pnl  # futures P&L settles to cash
            self.positions.remove(matched)
            self.trade_log.append({
                "date": order.trade_date, "time": order.trade_time,
                "symbol": order.symbol, "action": f"FUT_{order.action}_CLOSE",
                "price": price, "units": units, "cash_flow": pnl,
                "pnl": pnl, "entry_price": matched.entry_price,
                "entry_date": matched.entry_date,
                "hold_days": (order.trade_date - matched.entry_date).days,
                "tag": order.tag,
            })
        else:
            # Open a new futures leg (no cash outlay, margin ignored)
            self.positions.append(Position(
                symbol=order.symbol, expiry_key=order.expiry_key,
                strike=0, opt_type="FUT",
                action=order.action, qty_lots=order.qty,
                entry_price=price, entry_date=order.trade_date, units=units,
            ))
            self.trade_log.append({
                "date": order.trade_date, "time": order.trade_time,
                "symbol": order.symbol, "action": f"FUT_{order.action}_OPEN",
                "price": price, "units": units, "cash_flow": 0.0, "tag": order.tag,
            })

    def _find_position(
        self, symbol: str, strike: int, opt_type: str, action: str
    ) -> Position | None:
        for p in self.positions:
            if p.symbol == symbol and p.strike == strike and p.opt_type == opt_type and p.action == action:
                return p
        return None

    def mtm_value(self, chain: dict, synthetic_spot: float | None = None) -> float:
        """Mark all open positions to market."""
        from src.data.synthetic import find_atm
        if synthetic_spot is None:
            _, synthetic_spot = find_atm(chain)

        mtm = 0.0
        for pos in self.positions:
            if pos.opt_type == "FUT":
                # Mark futures vs current synthetic spot
                if synthetic_spot is not None:
                    current_price = synthetic_spot
                    if pos.action == "BUY":
                        mtm += (current_price - pos.entry_price) * pos.units
                    else:
                        mtm += (pos.entry_price - current_price) * pos.units
            else:
                bar = chain.get(pos.strike, {}).get(pos.opt_type)
                current_price = bar.get("close", pos.entry_price) if bar else pos.entry_price
                if pos.action == "BUY":
                    mtm += (current_price - pos.entry_price) * pos.units
                else:
                    mtm += (pos.entry_price - current_price) * pos.units
        return mtm

    def record_eod(self, trade_date: date, chain: dict) -> None:
        mtm = self.mtm_value(chain)
        equity = self.cash + mtm
        self.equity_curve.append({
            "date": trade_date,
            "cash": self.cash,
            "mtm": mtm,
            "equity": equity,
            "open_positions": len(self.positions),
        })

    def trade_log_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.trade_log) if self.trade_log else pd.DataFrame()

    def equity_df(self) -> pd.DataFrame:
        if not self.equity_curve:
            return pd.DataFrame()
        return pd.DataFrame(self.equity_curve).set_index("date")
