"""
Debit Spread Strategy — high-IV variant (bull call spread + bear put spread).

Used when straddle premium > high_iv_threshold of spot.
Structure:
  - Bull call spread: buy ATM CE, sell OTM CE (+1 interval)
  - Bear put spread:  buy ATM PE, sell OTM PE (+1 interval)

Adjustments when in position:
  - Delta hedge: buy ITM options (50pts ITM) every 75-pt spot move.
  - Sold-leg roll: when spot moves 75pts from entry strike, roll the short legs
    to new OTM strikes (+1 interval from new ATM) to avoid the sold leg going ATM/ITM.
"""

from __future__ import annotations

from datetime import date, time

from src.data.synthetic import find_atm, get_straddle_premium, straddle_as_pct_of_spot
from src.strategies.base import (
    DELTA_HEDGE_INTERVAL,
    STRIKE_INTERVAL,
    Order,
    Strategy,
    StrategyState,
)

TAKE_PROFIT_PCT = 0.30
STOP_LOSS_PCT = -0.50
SOLD_LEG_ROLL_THRESHOLD = 75   # roll short legs when spot moves 75pts from entry


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

            # 1. Check exits first
            exit_orders = self._check_exits(chain, trade_date, bar_time, state, spot)
            if exit_orders:
                return exit_orders

            # 2. Roll sold legs if spot moved 75pts from entry strike
            orders += self._check_sold_leg_roll(chain, trade_date, bar_time, state, spot)

            # 3. Delta hedge via ITM options every 75pts
            orders += self.delta_hedge_orders(chain, trade_date, bar_time, state, spot)

            return orders

        # ── Entry: Monday open, high-IV only ──
        if weekday != 0 or atm_strike is None or spot is None:
            return orders

        straddle = get_straddle_premium(chain, atm_strike)
        if straddle is None:
            return orders

        if straddle_as_pct_of_spot(straddle, spot) <= self.high_iv_threshold:
            return orders  # normal IV — let long straddle handle

        otm_strike = atm_strike + STRIKE_INTERVAL
        legs_spec = [
            (atm_strike, "CE", "BUY"),
            (otm_strike,  "CE", "SELL"),
            (atm_strike, "PE", "BUY"),
            (otm_strike,  "PE", "SELL"),
        ]

        net_premium = 0.0
        active_legs = []

        for strike, opt_type, action in legs_spec:
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
            active_legs.append({
                "strike": strike,
                "opt_type": opt_type,
                "action": action,
                "entry_price": price,
            })

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

    def _check_sold_leg_roll(
        self,
        chain: dict,
        trade_date: date,
        bar_time: time,
        state: StrategyState,
        spot: float,
    ) -> list[Order]:
        """
        Roll the short legs (sold OTM CE and sold OTM PE) when spot has moved
        75pts from the entry strike. The old sold leg risks going ATM/ITM;
        roll it to 1 interval OTM from the new ATM.
        """
        if abs(spot - state.entry_strike) < SOLD_LEG_ROLL_THRESHOLD:
            return []

        new_atm, _ = find_atm(chain)
        if new_atm is None:
            return []

        new_otm = new_atm + STRIKE_INTERVAL
        orders = []
        new_active_legs = []

        for leg in state.active_legs:
            if leg["action"] == "SELL":
                # Close old sold leg
                bar = chain.get(leg["strike"], {}).get(leg["opt_type"])
                price = bar.get("close", 0) if bar else 0
                orders.append(Order(
                    symbol=f"NIFTY{leg['strike']}{leg['opt_type']}",
                    expiry_key=state.expiry_key,
                    strike=leg["strike"],
                    opt_type=leg["opt_type"],
                    action="BUY",          # buy-to-close
                    qty=state.lots,
                    price=price,
                    trade_date=trade_date,
                    trade_time=bar_time,
                    tag="sold_roll_close",
                ))
                # Open new sold leg at new OTM
                new_bar = chain.get(new_otm, {}).get(leg["opt_type"])
                new_price = new_bar.get("close", 0) if new_bar else 0
                orders.append(Order(
                    symbol=f"NIFTY{new_otm}{leg['opt_type']}",
                    expiry_key=state.expiry_key,
                    strike=new_otm,
                    opt_type=leg["opt_type"],
                    action="SELL",
                    qty=state.lots,
                    price=new_price,
                    trade_date=trade_date,
                    trade_time=bar_time,
                    tag="sold_roll_open",
                ))
                new_active_legs.append({
                    "strike": new_otm,
                    "opt_type": leg["opt_type"],
                    "action": "SELL",
                    "entry_price": new_price,
                })
            else:
                new_active_legs.append(leg)  # bought legs unchanged

        if orders:
            state.active_legs = new_active_legs
            state.entry_strike = new_atm   # re-anchor for next roll check

        return orders

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

        orders += self.close_all_hedges(chain, trade_date, bar_time, state)
        state.reset()
        return orders
