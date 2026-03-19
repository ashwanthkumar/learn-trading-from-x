"""
Long Straddle Strategy — Sarang Sood's core long-gamma positional trade.

Entry: Monday open — buy ATM CE + ATM PE for nearest weekly expiry.
Regime: if straddle > high_iv_threshold% of spot → skip (let debit_spread handle).
ATM roll: if spot moves > 0.5% from entry strike → roll both legs.
Exit:
  1. P&L >= +30% of entry premium → take profit
  2. P&L <= -50% of entry premium → stop loss
  3. Thursday EOD (or Wednesday if Thursday is expiry) → close before weekend
"""

from __future__ import annotations

from datetime import date, time

from src.data.synthetic import find_atm, get_straddle_premium, straddle_as_pct_of_spot
from src.strategies.base import Order, Strategy, StrategyState

TAKE_PROFIT_PCT = 0.30   # +30% of entry premium
STOP_LOSS_PCT = -0.50    # -50% of entry premium
ROLL_THRESHOLD = 0.005   # 0.5% spot move triggers ATM roll
STRIKE_INTERVAL = 50     # Nifty strikes in 50-pt increments


class LongStraddleStrategy(Strategy):
    """
    Long gamma positional: buy ATM straddle on Monday, hold until exit signal.
    Defers to debit spread when IV is elevated.
    """

    def on_bar(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        expiry_key: str,
        state: StrategyState,
        portfolio,
    ) -> list[Order]:
        orders: list[Order] = []
        weekday = trade_date.weekday()  # 0=Mon, 3=Thu, 4=Fri

        # ── Check exit conditions when position is open ──
        if state.active_legs:
            orders += self._check_exits(chain, trade_date, bar_time, expiry_key, state)
            if not state.active_legs:
                return orders
            # Check ATM roll (only if still in position)
            orders += self._check_roll(chain, trade_date, bar_time, expiry_key, state)
            return orders

        # ── Entry: Monday open bar only ──
        if weekday != 0:
            return orders

        atm_strike, spot = find_atm(chain)
        if atm_strike is None or spot is None:
            return orders

        straddle = get_straddle_premium(chain, atm_strike)
        if straddle is None:
            return orders

        # Skip if IV is too high (let debit spread handle)
        if straddle_as_pct_of_spot(straddle, spot) > self.high_iv_threshold:
            return orders

        # Entry: buy ATM CE + PE
        for opt_type in ("CE", "PE"):
            bar = chain.get(atm_strike, {}).get(opt_type)
            if bar is None:
                return []  # Can't enter without both legs
            price = bar.get("close", 0)
            orders.append(Order(
                symbol=f"NIFTY{atm_strike}{opt_type}",
                expiry_key=expiry_key,
                strike=atm_strike,
                opt_type=opt_type,
                action="BUY",
                qty=self.lots,
                price=price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag="entry",
            ))

        # Update state
        state.active_legs = [
            {"strike": atm_strike, "opt_type": "CE", "entry_price": 0},
            {"strike": atm_strike, "opt_type": "PE", "entry_price": 0},
        ]
        state.entry_premium = straddle
        state.entry_date = trade_date
        state.entry_strike = atm_strike
        state.expiry_key = expiry_key
        state.lots = self.lots

        return orders

    def _current_pnl_pct(
        self, chain: dict, state: StrategyState
    ) -> float | None:
        """Calculate current MTM P&L as fraction of entry premium."""
        if state.entry_premium <= 0:
            return None

        total_current = 0.0
        for leg in state.active_legs:
            bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
            if bar is None:
                return None
            price = bar.get("close")
            if price is None:
                return None
            total_current += price

        entry = state.entry_premium
        # We're long both legs; P&L = (current_total - entry_total) / entry_total
        pnl_pct = (total_current - entry) / entry
        return pnl_pct

    def _check_exits(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        expiry_key: str,
        state: StrategyState,
    ) -> list[Order]:
        orders = []
        weekday = trade_date.weekday()
        expiry_date = date.fromisoformat(expiry_key)
        reason = None

        # 1. Time-based exit: close Thursday EOD (or Wednesday if Thu=expiry)
        is_expiry_thursday = (expiry_date.weekday() == 3 and expiry_date == trade_date)
        close_day = 2 if expiry_date.weekday() == 3 and expiry_date == trade_date else 3
        # Simpler: exit by Thursday (weekday 3) or on expiry day
        if weekday >= 3 or trade_date >= expiry_date:
            reason = "time_exit"

        # 2. Take profit / stop loss
        if reason is None:
            pnl_pct = self._current_pnl_pct(chain, state)
            if pnl_pct is not None:
                if pnl_pct >= TAKE_PROFIT_PCT:
                    reason = "take_profit"
                elif pnl_pct <= STOP_LOSS_PCT:
                    reason = "stop_loss"

        if reason is None:
            return []

        # Close all legs
        for leg in state.active_legs:
            bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
            price = bar.get("close", 0) if bar else 0
            orders.append(Order(
                symbol=f"NIFTY{leg['strike']}{leg['opt_type']}",
                expiry_key=state.expiry_key,
                strike=leg["strike"],
                opt_type=leg["opt_type"],
                action="SELL",
                qty=state.lots,
                price=price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag=reason,
            ))

        state.active_legs = []
        state.entry_premium = 0.0
        state.entry_strike = 0
        state.expiry_key = ""

        return orders

    def _check_roll(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        expiry_key: str,
        state: StrategyState,
    ) -> list[Order]:
        """Roll both legs to new ATM if spot has moved > 0.5% from entry strike."""
        atm_strike, spot = find_atm(chain)
        if atm_strike is None or spot is None:
            return []

        entry_strike = state.entry_strike
        if entry_strike == 0:
            return []

        move = abs(spot - entry_strike) / entry_strike
        if move <= ROLL_THRESHOLD:
            return []

        # Roll: close current legs, open new legs at new ATM
        orders = []
        new_straddle = get_straddle_premium(chain, atm_strike)

        for leg in state.active_legs:
            # Close old leg
            bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
            price = bar.get("close", 0) if bar else 0
            orders.append(Order(
                symbol=f"NIFTY{leg['strike']}{leg['opt_type']}",
                expiry_key=state.expiry_key,
                strike=leg["strike"],
                opt_type=leg["opt_type"],
                action="SELL",
                qty=state.lots,
                price=price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag="roll_close",
            ))
            # Open new leg at new ATM
            new_bar = chain.get(atm_strike, {}).get(leg["opt_type"])
            new_price = new_bar.get("close", 0) if new_bar else 0
            orders.append(Order(
                symbol=f"NIFTY{atm_strike}{leg['opt_type']}",
                expiry_key=state.expiry_key,
                strike=atm_strike,
                opt_type=leg["opt_type"],
                action="BUY",
                qty=state.lots,
                price=new_price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag="roll_open",
            ))

        # Update state
        state.active_legs = [
            {"strike": atm_strike, "opt_type": "CE", "entry_price": 0},
            {"strike": atm_strike, "opt_type": "PE", "entry_price": 0},
        ]
        state.entry_strike = atm_strike
        if new_straddle:
            state.entry_premium = new_straddle  # Reset P&L basis to rolled position

        return orders
