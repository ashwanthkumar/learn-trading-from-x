"""
Long Straddle Strategy — Sarang Sood's core long-gamma positional trade.

Positional mode (default):
  Entry: Monday open. Exit: Thursday EOD / expiry day.

Intraday mode (--intraday):
  Entry: any day, first bar at or before 09:30.
  Exit: 15:15 same day (or TP/SL hit intraday).

Both modes:
  Regime gate: straddle > high_iv_threshold of spot → skip (debit spread handles).
  ATM roll: when spot moves > 0.5% from current strike.
  Delta hedge: buy ITM options every 75-pt spot move.
  TP: +30% of entry premium. SL: -50% of entry premium.
"""

from __future__ import annotations

from datetime import date, time

from src.data.synthetic import find_atm, get_straddle_premium, straddle_as_pct_of_spot
from src.strategies.base import Order, Strategy, StrategyState

TAKE_PROFIT_PCT = 0.30
STOP_LOSS_PCT = -0.50
ROLL_THRESHOLD = 0.005
STRIKE_INTERVAL = 50


class LongStraddleStrategy(Strategy):

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
        atm_strike, spot = find_atm(chain)

        # ── Manage open position ──
        if state.active_legs:
            if spot is None:
                return orders
            exit_orders = self._check_exits(chain, trade_date, bar_time, state, spot)
            if exit_orders:
                return exit_orders
            orders += self._check_roll(chain, trade_date, bar_time, state, spot)
            orders += self.delta_hedge_orders(chain, trade_date, bar_time, state, spot)
            return orders

        # ── Entry ──
        if not self.can_enter(trade_date, bar_time, state):
            return orders
        if atm_strike is None or spot is None:
            return orders

        straddle = get_straddle_premium(chain, atm_strike)
        if straddle is None:
            return orders
        if straddle_as_pct_of_spot(straddle, spot) > self.high_iv_threshold:
            return orders  # elevated IV — let debit spread handle

        for opt_type in ("CE", "PE"):
            bar = chain.get(atm_strike, {}).get(opt_type)
            if bar is None:
                return []
            orders.append(Order(
                symbol=f"NIFTY{atm_strike}{opt_type}",
                expiry_key=expiry_key,
                strike=atm_strike,
                opt_type=opt_type,
                action="BUY",
                qty=self.lots,
                price=bar.get("close", 0),
                trade_date=trade_date,
                trade_time=bar_time,
                tag="entry",
            ))

        state.active_legs = [
            {"strike": atm_strike, "opt_type": "CE"},
            {"strike": atm_strike, "opt_type": "PE"},
        ]
        state.entry_premium = straddle
        state.entry_date = trade_date
        state.entry_strike = atm_strike
        state.expiry_key = expiry_key
        state.lots = self.lots
        state.last_hedge_spot = spot
        return orders

    def _current_pnl_pct(self, chain: dict, state: StrategyState) -> float | None:
        if state.entry_premium <= 0:
            return None
        total = 0.0
        for leg in state.active_legs:
            bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
            if bar is None:
                return None
            price = bar.get("close")
            if price is None:
                return None
            total += price
        return (total - state.entry_premium) / state.entry_premium

    def _check_exits(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        reason = None

        if self.is_time_exit(trade_date, bar_time, state.expiry_key):
            reason = "time_exit"

        if reason is None:
            pnl_pct = self._current_pnl_pct(chain, state)
            if pnl_pct is not None:
                if pnl_pct >= TAKE_PROFIT_PCT:
                    reason = "take_profit"
                elif pnl_pct <= STOP_LOSS_PCT:
                    reason = "stop_loss"

        if reason is None:
            return []

        orders = []
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
        orders += self.close_all_hedges(chain, trade_date, bar_time, state)
        state.reset()
        return orders

    def _check_roll(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        if state.entry_strike == 0:
            return []
        move = abs(spot - state.entry_strike) / state.entry_strike
        if move <= ROLL_THRESHOLD:
            return []
        atm_strike, _ = find_atm(chain)
        if atm_strike is None or atm_strike == state.entry_strike:
            return []

        orders = []
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
                tag="roll_close",
            ))
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

        new_straddle = get_straddle_premium(chain, atm_strike)
        state.active_legs = [
            {"strike": atm_strike, "opt_type": "CE"},
            {"strike": atm_strike, "opt_type": "PE"},
        ]
        state.entry_strike = atm_strike
        if new_straddle:
            state.entry_premium = new_straddle
        state.last_hedge_spot = spot
        return orders
