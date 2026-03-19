"""
Portfolio: tracks positions, cash, and MTM P&L.

Lot sizes:
  - Pre-Oct 2024: 50 units per lot
  - Oct 2024 onwards: 75 units per lot
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    opt_type: str
    action: Literal["BUY", "SELL"]
    qty_lots: int
    entry_price: float
    entry_date: date
    units: int  # qty_lots * lot_size


@dataclass
class Trade:
    entry_order: Order
    exit_order: Order | None
    entry_price: float
    exit_price: float | None
    units: int
    pnl: float | None  # realised P&L in rupees


class Portfolio:
    def __init__(self, initial_cash: float = 1_000_000.0):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: list[Position] = []
        self.trade_log: list[dict] = []
        self.equity_curve: list[dict] = []

    def execute(self, order: Order) -> None:
        """Execute an order, update cash and positions."""
        units = order.qty * lot_size(order.trade_date)
        price = order.price

        if order.action == "BUY":
            # Debit cash, open long position
            cost = price * units
            self.cash -= cost
            self.positions.append(Position(
                symbol=order.symbol,
                expiry_key=order.expiry_key,
                strike=order.strike,
                opt_type=order.opt_type,
                action="BUY",
                qty_lots=order.qty,
                entry_price=price,
                entry_date=order.trade_date,
                units=units,
            ))
            self.trade_log.append({
                "date": order.trade_date,
                "time": order.trade_time,
                "symbol": order.symbol,
                "action": "BUY",
                "price": price,
                "units": units,
                "cash_flow": -cost,
                "tag": order.tag,
            })

        elif order.action == "SELL":
            # Find matching long position to close
            matched = self._find_position(order.symbol, order.strike, order.opt_type, "BUY")
            if matched:
                proceeds = price * units
                self.cash += proceeds
                pnl = (price - matched.entry_price) * units
                self.positions.remove(matched)
                self.trade_log.append({
                    "date": order.trade_date,
                    "time": order.trade_time,
                    "symbol": order.symbol,
                    "action": "SELL",
                    "price": price,
                    "units": units,
                    "cash_flow": proceeds,
                    "pnl": pnl,
                    "entry_price": matched.entry_price,
                    "entry_date": matched.entry_date,
                    "hold_days": (order.trade_date - matched.entry_date).days,
                    "tag": order.tag,
                })
            else:
                # Short position (for debit spread sold legs)
                self.cash += price * units  # Receive premium
                self.positions.append(Position(
                    symbol=order.symbol,
                    expiry_key=order.expiry_key,
                    strike=order.strike,
                    opt_type=order.opt_type,
                    action="SELL",
                    qty_lots=order.qty,
                    entry_price=price,
                    entry_date=order.trade_date,
                    units=units,
                ))
                self.trade_log.append({
                    "date": order.trade_date,
                    "time": order.trade_time,
                    "symbol": order.symbol,
                    "action": "SELL",
                    "price": price,
                    "units": units,
                    "cash_flow": price * units,
                    "tag": order.tag,
                })

        elif order.action == "BUY" and self._find_position(order.symbol, order.strike, order.opt_type, "SELL"):
            # Close a short position
            matched = self._find_position(order.symbol, order.strike, order.opt_type, "SELL")
            cost = price * units
            self.cash -= cost
            pnl = (matched.entry_price - price) * units
            self.positions.remove(matched)
            self.trade_log.append({
                "date": order.trade_date,
                "time": order.trade_time,
                "symbol": order.symbol,
                "action": "BUY_CLOSE",
                "price": price,
                "units": units,
                "cash_flow": -cost,
                "pnl": pnl,
                "entry_price": matched.entry_price,
                "entry_date": matched.entry_date,
                "hold_days": (order.trade_date - matched.entry_date).days,
                "tag": order.tag,
            })

    def _find_position(
        self, symbol: str, strike: int, opt_type: str, action: str
    ) -> Position | None:
        for p in self.positions:
            if p.symbol == symbol and p.strike == strike and p.opt_type == opt_type and p.action == action:
                return p
        return None

    def mtm_value(self, chain: dict) -> float:
        """Mark all open positions to market using current chain prices."""
        mtm = 0.0
        for pos in self.positions:
            bar = chain.get(pos.strike, {}).get(pos.opt_type)
            if bar is None:
                current_price = pos.entry_price  # assume no change
            else:
                current_price = bar.get("close", pos.entry_price)
            if pos.action == "BUY":
                mtm += (current_price - pos.entry_price) * pos.units
            else:
                mtm += (pos.entry_price - current_price) * pos.units
        return mtm

    def record_eod(self, trade_date: date, chain: dict) -> None:
        """Append an equity curve data point at EOD."""
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
        if not self.trade_log:
            return pd.DataFrame()
        return pd.DataFrame(self.trade_log)

    def equity_df(self) -> pd.DataFrame:
        if not self.equity_curve:
            return pd.DataFrame()
        return pd.DataFrame(self.equity_curve).set_index("date")
