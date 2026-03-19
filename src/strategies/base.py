"""Abstract Strategy interface with shared delta-hedge logic."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, time
from typing import Literal

# Delta-hedge parameters
DELTA_HEDGE_INTERVAL = 75   # trigger a hedge every 75-pt spot move
DELTA_HEDGE_LOTS = 1        # lots of ITM options per hedge leg
STRIKE_INTERVAL = 50        # Nifty strike grid

# Intraday mode timing
INTRADAY_ENTRY_CUTOFF = time(9, 30)   # only enter before this time
INTRADAY_EXIT_TIME = time(15, 15)     # force-exit at or after this time


@dataclass
class Order:
    """Represents a single trade order."""
    symbol: str             # e.g. 'NIFTY24010419000CE'
    expiry_key: str         # e.g. '2024-01-04'
    strike: int
    opt_type: Literal["CE", "PE"]
    action: Literal["BUY", "SELL"]
    qty: int                # number of lots
    price: float            # execution price
    trade_date: date
    trade_time: time
    tag: str = ""           # entry / exit / roll / delta_hedge / hedge_close


@dataclass
class StrategyState:
    """Mutable state passed between on_bar calls."""
    active_legs: list[dict] = field(default_factory=list)
    entry_premium: float = 0.0
    entry_date: date | None = None
    entry_strike: int = 0
    expiry_key: str = ""
    lots: int = 1
    # Delta-hedge state
    last_hedge_spot: float = 0.0    # spot at which last hedge was triggered
    hedge_legs: list[dict] = field(default_factory=list)
    # Each element: {"strike": int, "opt_type": "CE"|"PE", "qty": int, "entry_price": float}

    def reset(self) -> None:
        """Clear all position and hedge state after a full close."""
        self.active_legs = []
        self.entry_premium = 0.0
        self.entry_strike = 0
        self.expiry_key = ""
        self.last_hedge_spot = 0.0
        self.hedge_legs = []


HEDGE_STRIKE_GRID = 100  # ITM hedge options snap to 100pt strike intervals


def _itm_pe_strike(spot: float) -> int:
    """
    PE is ITM when strike > spot.
    Target ~100-150pts ITM, snapped to the next 100pt strike above (spot + 100).
    e.g. spot=21825 → spot+100=21925 → ceil to 100pt grid → 22000 (175pts ITM)
         spot=21900 → spot+100=22000 → 22000 (100pts ITM)
    """
    return int(math.ceil((spot + HEDGE_STRIKE_GRID) / HEDGE_STRIKE_GRID) * HEDGE_STRIKE_GRID)


def _itm_ce_strike(spot: float) -> int:
    """
    CE is ITM when strike < spot.
    Target ~100-150pts ITM, snapped to the next 100pt strike below (spot - 100).
    e.g. spot=21825 → spot-100=21725 → floor to 100pt grid → 21700 (125pts ITM)
         spot=21900 → spot-100=21800 → 21800 (100pts ITM)
    """
    return int(math.floor((spot - HEDGE_STRIKE_GRID) / HEDGE_STRIKE_GRID) * HEDGE_STRIKE_GRID)


class Strategy(ABC):
    """Base class for all strategies. Includes shared delta-hedge logic."""

    def __init__(
        self,
        lots: int = 1,
        high_iv_threshold: float = 0.025,
        intraday: bool = False,
    ):
        self.lots = lots
        self.high_iv_threshold = high_iv_threshold
        self.intraday = intraday  # True → enter/exit same day; False → positional

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
        """Called for every 1-min bar. Returns orders queued for t+2 fill."""
        ...

    def select_nearest_expiry(self, index: dict, trade_date: date) -> str | None:
        future_expiries = [k for k in index if k >= trade_date.strftime("%Y-%m-%d")]
        return min(future_expiries) if future_expiries else None

    def can_enter(self, trade_date: date, bar_time: time, state: StrategyState) -> bool:
        """Return True if this bar is a valid entry point."""
        if state.active_legs:
            return False
        if self.intraday:
            return bar_time <= INTRADAY_ENTRY_CUTOFF
        else:
            return trade_date.weekday() == 0  # Monday only

    def is_time_exit(self, trade_date: date, bar_time: time, expiry_key: str) -> bool:
        """Return True if the time-based exit condition is met."""
        if self.intraday:
            return bar_time >= INTRADAY_EXIT_TIME
        else:
            expiry_date = date.fromisoformat(expiry_key)
            return trade_date.weekday() >= 3 or trade_date >= expiry_date

    def delta_hedge_orders(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        """
        Buy ITM options to offset accumulated delta every 75-pt spot move.

        When spot moves UP 75pts from last hedge:
          - We're net long delta (CE gained, PE lost)
          - Buy 1 lot ITM PE (strike just above current spot) → negative delta offset

        When spot moves DOWN 75pts from last hedge:
          - We're net short delta (PE gained, CE lost)
          - Buy 1 lot ITM CE (strike just below current spot) → positive delta offset

        The hedge position is held until the main position is closed.
        """
        if not state.active_legs:
            return []

        # Anchor on first bar after entry
        if state.last_hedge_spot == 0.0:
            state.last_hedge_spot = spot
            return []

        orders = []
        move = spot - state.last_hedge_spot

        while abs(move) >= DELTA_HEDGE_INTERVAL:
            if move > 0:
                # Spot up → buy ITM PE
                hedge_strike = _itm_pe_strike(spot)
                opt_type = "PE"
                state.last_hedge_spot += DELTA_HEDGE_INTERVAL
            else:
                # Spot down → buy ITM CE
                hedge_strike = _itm_ce_strike(spot)
                opt_type = "CE"
                state.last_hedge_spot -= DELTA_HEDGE_INTERVAL

            bar = chain.get(hedge_strike, {}).get(opt_type)
            price = bar.get("close", 0) if bar else 0

            if price > 0:
                orders.append(Order(
                    symbol=f"NIFTY{hedge_strike}{opt_type}",
                    expiry_key=state.expiry_key,
                    strike=hedge_strike,
                    opt_type=opt_type,
                    action="BUY",
                    qty=DELTA_HEDGE_LOTS,
                    price=price,
                    trade_date=trade_date,
                    trade_time=bar_time,
                    tag="delta_hedge",
                ))
                state.hedge_legs.append({
                    "strike": hedge_strike,
                    "opt_type": opt_type,
                    "qty": DELTA_HEDGE_LOTS,
                    "entry_price": price,
                })

            move = spot - state.last_hedge_spot

        return orders

    def close_all_hedges(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
    ) -> list[Order]:
        """Sell all open ITM hedge option positions."""
        orders = []
        for leg in state.hedge_legs:
            bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
            price = bar.get("close", 0) if bar else 0
            orders.append(Order(
                symbol=f"NIFTY{leg['strike']}{leg['opt_type']}",
                expiry_key=state.expiry_key,
                strike=leg["strike"],
                opt_type=leg["opt_type"],
                action="SELL",
                qty=leg["qty"],
                price=price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag="hedge_close",
            ))
        state.hedge_legs = []
        state.last_hedge_spot = 0.0
        return orders
