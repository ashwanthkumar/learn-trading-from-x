"""Abstract Strategy interface with shared delta-hedge logic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, time
from typing import Literal

DELTA_HEDGE_INTERVAL = 50   # hedge every 50-point spot move
DELTA_HEDGE_LOTS = 1        # lots of futures per hedge trade


@dataclass
class Order:
    """Represents a single trade order (option or futures)."""
    symbol: str             # e.g. 'NIFTY24010419000CE' or 'NIFTY-FUT'
    expiry_key: str         # e.g. '2024-01-04'
    strike: int             # 0 for futures
    opt_type: Literal["CE", "PE", "FUT"]
    action: Literal["BUY", "SELL"]
    qty: int                # number of lots
    price: float            # execution price
    trade_date: date
    trade_time: time
    tag: str = ""           # entry/exit/roll/delta_hedge


@dataclass
class StrategyState:
    """Mutable state passed between on_bar calls."""
    active_legs: list[dict] = field(default_factory=list)
    entry_premium: float = 0.0
    entry_date: date | None = None
    entry_strike: int = 0
    expiry_key: str = ""
    lots: int = 1
    # Delta hedging
    last_hedge_spot: float = 0.0    # synthetic spot price at last hedge trade
    net_hedge_lots: int = 0         # cumulative futures position (+ long, - short)

    def reset(self) -> None:
        """Clear position state after a full close."""
        self.active_legs = []
        self.entry_premium = 0.0
        self.entry_strike = 0
        self.expiry_key = ""
        self.last_hedge_spot = 0.0
        self.net_hedge_lots = 0


class Strategy(ABC):
    """Base class for all strategies. Includes shared delta-hedge logic."""

    def __init__(self, lots: int = 1, high_iv_threshold: float = 0.025):
        self.lots = lots
        self.high_iv_threshold = high_iv_threshold  # straddle > threshold → high IV regime

    @abstractmethod
    def on_bar(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        expiry_key: str,
        state: StrategyState,
        portfolio,
    ) -> list[Order]:
        """Called for every 1-min bar. Returns orders to queue for t+2 fill."""
        ...

    def select_nearest_expiry(self, index: dict, trade_date: date) -> str | None:
        future_expiries = [k for k in index if k >= trade_date.strftime("%Y-%m-%d")]
        return min(future_expiries) if future_expiries else None

    def delta_hedge_orders(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        """
        Emit a futures order if spot has moved >= 50pts from the last hedge price.

        Logic:
          - Spot up 50 → we're net long delta (CE gained more than PE lost) → SELL futures
          - Spot down 50 → we're net short delta → BUY futures

        Each hedge is exactly DELTA_HEDGE_LOTS lots of Nifty futures.
        The hedge price is the current synthetic spot (used as futures proxy).
        """
        if not state.active_legs or state.last_hedge_spot == 0.0:
            # Initialise hedge anchor on first bar after entry
            if state.active_legs and state.last_hedge_spot == 0.0:
                state.last_hedge_spot = spot
            return []

        move = spot - state.last_hedge_spot
        orders = []

        while abs(move) >= DELTA_HEDGE_INTERVAL:
            if move > 0:
                # Spot went up → sell futures to offset long delta
                action = "SELL"
                state.net_hedge_lots -= DELTA_HEDGE_LOTS
                state.last_hedge_spot += DELTA_HEDGE_INTERVAL
            else:
                # Spot went down → buy futures to offset short delta
                action = "BUY"
                state.net_hedge_lots += DELTA_HEDGE_LOTS
                state.last_hedge_spot -= DELTA_HEDGE_INTERVAL

            orders.append(Order(
                symbol="NIFTY-FUT",
                expiry_key=state.expiry_key,
                strike=0,
                opt_type="FUT",
                action=action,
                qty=DELTA_HEDGE_LOTS,
                price=spot,
                trade_date=trade_date,
                trade_time=bar_time,
                tag="delta_hedge",
            ))
            move = spot - state.last_hedge_spot

        return orders

    def close_all_hedges(
        self,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        """Flatten all open delta-hedge futures positions."""
        orders = []
        net = state.net_hedge_lots
        if net == 0:
            return orders

        # net > 0 means we're long futures → sell to close
        # net < 0 means we're short futures → buy to close
        action = "SELL" if net > 0 else "BUY"
        orders.append(Order(
            symbol="NIFTY-FUT",
            expiry_key=state.expiry_key,
            strike=0,
            opt_type="FUT",
            action=action,
            qty=abs(net),
            price=spot,
            trade_date=trade_date,
            trade_time=bar_time,
            tag="hedge_close",
        ))
        state.net_hedge_lots = 0
        state.last_hedge_spot = 0.0
        return orders
