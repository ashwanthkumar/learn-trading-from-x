"""Abstract Strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, time
from typing import Literal


@dataclass
class Order:
    """Represents a single trade order."""
    symbol: str          # e.g. 'NIFTY24010419000CE'
    expiry_key: str      # e.g. '2024-01-04'
    strike: int
    opt_type: Literal["CE", "PE"]
    action: Literal["BUY", "SELL"]
    qty: int             # number of lots
    price: float         # execution price (0 = market)
    trade_date: date
    trade_time: time
    tag: str = ""        # label for tracking (entry/exit/roll)


@dataclass
class StrategyState:
    """Mutable state passed between on_bar calls."""
    active_legs: list[dict] = field(default_factory=list)
    entry_premium: float = 0.0
    entry_date: date | None = None
    entry_strike: int = 0
    expiry_key: str = ""
    lots: int = 1


class Strategy(ABC):
    """Base class for all strategies."""

    def __init__(self, lots: int = 1, high_iv_threshold: float = 0.025):
        self.lots = lots
        self.high_iv_threshold = high_iv_threshold  # straddle > 2.5% of spot → high IV

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
        """
        Called for every trading bar. Returns a list of orders to execute.
        Mutates state as needed.
        """
        ...

    def select_nearest_expiry(self, index: dict, trade_date: date) -> str | None:
        """
        Return the expiry_key for the nearest upcoming expiry on or after trade_date.
        """
        future_expiries = [
            k for k in index
            if k >= trade_date.strftime("%Y-%m-%d")
        ]
        if not future_expiries:
            return None
        return min(future_expiries)
