"""
Debit Spread Strategy — high-IV variant (bull call spread + bear put spread).

Used when straddle premium > high_iv_threshold of spot.
Structure:
  - Bull call spread: buy ATM CE, sell OTM CE (+1 interval)
  - Bear put spread:  buy ATM PE, sell OTM PE (+1 interval)

Delta hedge: sell/buy 1 lot Nifty futures per 50-pt spot move.
Same exit rules as long straddle.
"""

from __future__ import annotations

from datetime import date, time

from src.data.synthetic import find_atm, get_straddle_premium, straddle_as_pct_of_spot
from src.strategies.base import Order, Strategy, StrategyState

TAKE_PROFIT_PCT = 0.30
STOP_LOSS_PCT = -0.50
STRIKE_INTERVAL = 50


class DebitSpreadStrategy(Strategy):

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
        weekday = trade_date.weekday()

        atm_strike, spot = find_atm(chain)

        # ── Manage open position ──
        if state.active_legs:
            if spot is None:
                return orders

            exit_orders = self._check_exits(chain, trade_date, bar_time, state, spot)
            if exit_orders:
                return exit_orders

            # Delta hedge every 50-pt move
            orders += self.delta_hedge_orders(chain, trade_date, bar_time, state, spot)
            return orders

        # ── Entry: Monday open, high-IV only ──
        if weekday != 0 or atm_strike is None or spot is None:
            return orders

        straddle = get_straddle_premium(chain, atm_strike)
        if straddle is None:
            return orders

        if straddle_as_pct_of_spot(straddle, spot) <= self.high_iv_threshold:
            return orders  # normal IV, let long straddle handle

        otm_strike = atm_strike + STRIKE_INTERVAL
        legs = [
            (atm_strike, "CE", "BUY"),
            (otm_strike,  "CE", "SELL"),
            (atm_strike, "PE", "BUY"),
            (otm_strike,  "PE", "SELL"),
        ]

        net_premium = 0.0
        active_legs = []

        for strike, opt_type, action in legs:
            bar = chain.get(strike, {}).get(opt_type)
            if bar is None:
                return []
            price = bar.get("close", 0)
            sign = 1 if action == "BUY" else -1
            net_premium += sign * price
            orders.append(Order(
                symbol=f"NIFTY{strike}{opt_type}",
                expiry_key=expiry_key,
                strike=strike,
                opt_type=opt_type,
                action=action,
                qty=self.lots,
                price=price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag="entry",
            ))
            active_legs.append({"strike": strike, "opt_type": opt_type, "action": action})

        state.active_legs = active_legs
        state.entry_premium = abs(net_premium)
        state.entry_date = trade_date
        state.entry_strike = atm_strike
        state.expiry_key = expiry_key
        state.lots = self.lots
        state.last_hedge_spot = spot

        return orders

    def _current_pnl_pct(self, chain: dict, state: StrategyState) -> float | None:
        if state.entry_premium <= 0:
            return None
        total_pnl = 0.0
        for leg in state.active_legs:
            bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
            if bar is None:
                return None
            price = bar.get("close")
            if price is None:
                return None
            entry_price = leg.get("entry_price", 0)
            sign = 1 if leg["action"] == "BUY" else -1
            total_pnl += sign * (price - entry_price)
        return total_pnl / state.entry_premium

    def _check_exits(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        weekday = trade_date.weekday()
        expiry_date = date.fromisoformat(state.expiry_key)
        reason = None

        if weekday >= 3 or trade_date >= expiry_date:
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
            close_action = "SELL" if leg["action"] == "BUY" else "BUY"
            orders.append(Order(
                symbol=f"NIFTY{leg['strike']}{leg['opt_type']}",
                expiry_key=state.expiry_key,
                strike=leg["strike"],
                opt_type=leg["opt_type"],
                action=close_action,
                qty=state.lots,
                price=price,
                trade_date=trade_date,
                trade_time=bar_time,
                tag=reason,
            ))

        orders += self.close_all_hedges(trade_date, bar_time, state, spot)
        state.reset()
        return orders
