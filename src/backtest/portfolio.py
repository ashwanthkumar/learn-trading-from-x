"""
Portfolio: tracks option positions, cash, and MTM P&L.

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
    cutoff = date(2024, 10, 1)
    return 75 if trade_date >= cutoff else 50


@dataclass
class Position:
    symbol: str
    expiry_key: str
    strike: int
    opt_type: str               # CE or PE
    action: Literal["BUY", "SELL"]
    qty_lots: int
    entry_price: float
    entry_date: date
    units: int                  # qty_lots * lot_size


class Portfolio:
    def __init__(self, initial_cash: float = 1_000_000.0):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: list[Position] = []
        self.trade_log: list[dict] = []
        self.equity_curve: list[dict] = []

    def execute(self, order: Order) -> None:
        units = order.qty * lot_size(order.trade_date)
        price = order.price

        if order.action == "BUY":
            # Try to close an existing short position first (buy-to-close)
            matched_short = self._find_position(order.symbol, order.strike, order.opt_type, "SELL")
            if matched_short:
                self._close_short(order, matched_short, units, price)
            else:
                self._open_long(order, units, price)

        elif order.action == "SELL":
            # Try to close an existing long position first (sell-to-close)
            matched_long = self._find_position(order.symbol, order.strike, order.opt_type, "BUY")
            if matched_long:
                self._close_long(order, matched_long, units, price)
            else:
                self._open_short(order, units, price)

    def _open_long(self, order: Order, units: int, price: float) -> None:
        self.cash -= price * units
        self.positions.append(Position(
            symbol=order.symbol, expiry_key=order.expiry_key,
            strike=order.strike, opt_type=order.opt_type,
            action="BUY", qty_lots=order.qty,
            entry_price=price, entry_date=order.trade_date, units=units,
        ))
        self.trade_log.append({
            "date": order.trade_date, "time": order.trade_time,
            "symbol": order.symbol, "action": "BUY",
            "price": price, "units": units,
            "cash_flow": -(price * units), "tag": order.tag,
        })

    def _close_long(self, order: Order, matched: Position, units: int, price: float) -> None:
        proceeds = price * units
        pnl = (price - matched.entry_price) * units
        self.cash += proceeds
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

    def _close_short(self, order: Order, matched: Position, units: int, price: float) -> None:
        cost = price * units
        pnl = (matched.entry_price - price) * units  # profit when buying back cheaper
        self.cash -= cost
        self.positions.remove(matched)
        self.trade_log.append({
            "date": order.trade_date, "time": order.trade_time,
            "symbol": order.symbol, "action": "BUY_CLOSE",
            "price": price, "units": units, "cash_flow": -cost,
            "pnl": pnl, "entry_price": matched.entry_price,
            "entry_date": matched.entry_date,
            "hold_days": (order.trade_date - matched.entry_date).days,
            "tag": order.tag,
        })

    def _find_position(
        self, symbol: str, strike: int, opt_type: str, action: str
    ) -> Position | None:
        for p in self.positions:
            if (p.symbol == symbol and p.strike == strike
                    and p.opt_type == opt_type and p.action == action):
                return p
        return None

    def mtm_value(self, chain: dict) -> float:
        mtm = 0.0
        for pos in self.positions:
            bar = chain.get(pos.strike, {}).get(pos.opt_type)
            current_price = bar.get("close", pos.entry_price) if bar else pos.entry_price
            if pos.action == "BUY":
                mtm += (current_price - pos.entry_price) * pos.units
            else:
                mtm += (pos.entry_price - current_price) * pos.units
        return mtm

    def record_eod(self, trade_date: date, chain: dict) -> None:
        mtm = self.mtm_value(chain)
        self.equity_curve.append({
            "date": trade_date,
            "cash": self.cash,
            "mtm": mtm,
            "equity": self.cash + mtm,
            "open_positions": len(self.positions),
        })

    def trade_log_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.trade_log) if self.trade_log else pd.DataFrame()

    def equity_df(self) -> pd.DataFrame:
        if not self.equity_curve:
            return pd.DataFrame()
        return pd.DataFrame(self.equity_curve).set_index("date")
