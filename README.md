# Nifty Options Backtester — Sarang Sood Strategy

Backtesting engine for Sarang Sood's long-gamma / long-vega positional strategies on Nifty weekly options. Uses 1-minute OHLCV+OI data from eodieod.com historical archives.

---

## Quick Start

```bash
# Run long straddle on Q1 2024
uv run main.py --from 2024-01 --to 2024-03 --strategy long_straddle

# Run debit spread (high-IV variant)
uv run main.py --from 2024-01 --to 2024-03 --strategy debit_spread

# Run both strategies and compare
uv run main.py --from 2024-01 --to 2024-12 --strategy both

# Custom lot size and capital
uv run main.py --from 2024-01 --to 2024-03 --strategy long_straddle --lots 2 --capital 2000000

# Adjust IV threshold (default 2.5%)
uv run main.py --from 2024-01 --to 2024-03 --strategy long_straddle --iv-threshold 0.03
```

Output is written to `output/`:
- `trade_log_<strategy>_<dates>.csv` — every order with entry price, exit price, P&L, hold days
- `equity_curve_<strategy>_<dates>.png` — equity curve + drawdown chart

---

## Strategies

### 1. Long Straddle (`long_straddle`)

**Philosophy:** Sarang's core long-gamma positional trade. Buy both sides of ATM and wait for a large, fast move. Profits from volatility expansion (long vega) and large directional moves (long gamma). Used in normal/low IV environments where premiums are affordable.

> *"I'm mostly long gamma specially in this environment, so fast moves is what I wait for."* — Sarang Sood, Mar 2026

**Entry Conditions:**
- Day: Monday open (first bar of the trading week)
- Instrument: Buy ATM CE + ATM PE for the nearest weekly Nifty expiry
- ATM identification: synthetic future method — find strike where `|CE_close − PE_close|` is minimised; `F = K + CE − PE`
- IV regime gate: straddle premium must be **≤ iv-threshold** (default 2.5%) of synthetic spot; if above threshold, skip and let debit spread handle

**Exit Conditions (in order of priority):**

| Condition | Trigger | Reason |
|-----------|---------|--------|
| Take profit | Current straddle value ≥ +30% of entry premium | Lock in gamma gains |
| Stop loss | Current straddle value ≤ −50% of entry premium | Avoid theta destruction |
| Time exit | Thursday EOD (or expiry day) | No weekend gamma/theta exposure |
| ATM roll | Spot moves > 0.5% from entry strike | Stay near ATM; delta ~50 on both legs |

**ATM Roll:** When spot moves far enough, close both legs at current prices and re-open at the new ATM strike. The entry premium basis resets to the new position cost. This implements Sarang's principle: *"The strikes keep adjusting around that figure [delta 50]."*

**Lot sizes:**
- Pre-October 2024: 50 units/lot
- October 2024 onward: 75 units/lot

---

### 2. Debit Spread (`debit_spread`)

**Philosophy:** High-IV variant — same long-gamma intent but with reduced premium outflow. When options are expensive, buying naked straddles bleeds heavily from theta. Selling the wings (OTM CE and OTM PE) offsets some of the premium cost while preserving the long-gamma character.

> *"During high premiums I trade in debit spreads more. So the gamma on that move was actually good for me."* — Sarang Sood, Mar 2026

**Structure:** 4-legged position:
- Buy ATM CE (long delta, long gamma, long vega)
- Sell OTM CE (+50 strike) — reduces vega and theta cost on call side
- Buy ATM PE (short delta, long gamma, long vega)
- Sell OTM PE (+50 strike) — reduces vega and theta cost on put side

Net position: long gamma (bounded), long vega (bounded), reduced theta bleed vs naked straddle.

**Entry Conditions:**
- Day: Monday open
- Instrument: 4-leg debit spread as described above
- IV regime gate: straddle premium must be **> iv-threshold** (default 2.5%) of synthetic spot — only enters when IV is elevated (complement to long straddle)

**Exit Conditions:** Same as long straddle:

| Condition | Trigger |
|-----------|---------|
| Take profit | Net P&L ≥ +30% of net debit paid |
| Stop loss | Net P&L ≤ −50% of net debit paid |
| Time exit | Thursday EOD or expiry day |

No ATM roll in debit spread (the spread caps max profit/loss; rolling is complex and typically not used in this structure).

---

## IV Regime Switching

The two strategies are designed to complement each other. The `--iv-threshold` flag controls the regime boundary:

```
straddle_premium / synthetic_spot:

  < threshold  →  Long Straddle enters, Debit Spread skips
  ≥ threshold  →  Debit Spread enters, Long Straddle skips
```

Run `--strategy both` to let each trade in its own regime simultaneously (using separate portfolio instances).

**VIX note:** The backtest has no India VIX data. The straddle-as-% of spot serves as a proxy. Sarang uses VIX > 20 as a capital preservation signal; you can approximate this by increasing `--iv-threshold` in high-vol periods. Sarang's calibration: *"India VIX: 22, Nifty: 23200, Straddle: 500"* ≈ straddle at 2.2% of spot.

---

## Data

**Source:** `eodieod.com` historical archives in `/Users/ashwanthkumar/Downloads/eodieod.com-historical-data/`

**Format:** 1-minute OHLCV+OI bars per strike per expiry, stored as:
```
{YEAR}/Index Option IEoD - {YYMM}.rar
  └── NIFTY{YY}{MM}{DD}{STRIKE}{CE|PE}.csv
```

Where `{MM}{DD}` is the **expiry date** (2-digit month, 2-digit day).

**Extraction:** RARs are automatically extracted to `.cache/extracted/{YYMM}/` on first run. Subsequent runs reuse the cache. Only `NIFTY*` files are extracted (BANKNIFTY, FINNIFTY, MIDCPNIFTY are skipped).

**Synthetic ATM:** Spot price is derived via put-call parity: scan all strikes for `min|CE_close − PE_close|`; synthetic future `F = K + CE − PE`. This avoids needing separate spot data and correctly accounts for cost of carry (spot ≠ futures price).

---

## Project Structure

```
src/
├── data/
│   ├── loader.py      # RAR extraction, file indexing
│   ├── chain.py       # Option chain builder (1-min bars per strike per date)
│   └── synthetic.py   # Synthetic spot/ATM via put-call parity
├── strategies/
│   ├── base.py        # Strategy ABC, Order/StrategyState dataclasses
│   ├── long_straddle.py  # Long gamma positional
│   └── debit_spread.py   # High-IV debit spread
├── backtest/
│   ├── engine.py      # Day/bar iterator, order execution
│   ├── portfolio.py   # Position tracking, cash, MTM P&L
│   └── metrics.py     # Sharpe, CAGR, drawdown, win rate
└── analysis/
    └── report.py      # Prints summary, saves PNG + trade CSV
main.py                # CLI entry point
```

---

## Metrics Reported

| Metric | Description |
|--------|-------------|
| `total_return_pct` | (Final equity / Initial capital − 1) × 100 |
| `cagr_pct` | Annualised compound return |
| `sharpe` | Annualised Sharpe ratio (0% risk-free) |
| `max_drawdown_pct` | Peak-to-trough drawdown |
| `total_trades` | Number of closed legs |
| `win_rate_pct` | % of trades with positive P&L |
| `avg_pnl` | Average P&L per closed trade (₹) |
| `avg_hold_days` | Average days held per trade |

---

## Known Limitations

1. **EOD bars only:** The engine uses end-of-day chain snapshots (15:25 bar). Intraday entry/exit timing is not modelled — all orders execute at the EOD price of the signal bar.
2. **No slippage / transaction costs:** Options have wide bid-ask spreads; real execution will be worse than modelled prices.
3. **No India VIX data:** IV regime is proxied via straddle premium as % of spot. The straddle signal is correlated with VIX but not identical.
4. **ATM roll simplification:** Rolls execute at the same bar's close (no next-bar slippage). In practice, rolling costs more.
5. **Delta hedging not modelled:** Sarang's algo does active delta hedging (gamma scalping). This backtester only tracks the option legs, not delta hedges.
6. **Monthly expiry vs weekly:** The engine selects the nearest expiry on or after the trade date. Ensure the RAR for the relevant month is available in the data directory.

---

## Background: Sarang Sood's Strategy (Source Notes)

Based on tweets 2015–2026 compiled in `docs/sarang.md`:

- **Started as option seller** (pre-2015) with adjustments as edge
- **2015 China Black Monday** changed his view — realised theta decay alone is not an edge
- **2016–2020:** Ratio spreads in rising vol environments
- **2021–2023:** Expiry-day intraday, reading ATM straddle as primary IV gauge
- **2024–2026:** Full pivot to **long gamma / long vega**, algo-assisted, positional multi-day

Key principles implemented in this backtester:
- Stay ATM via strike rolling (delta ~50 on both legs)
- Adapt structure to IV regime (plain straddle vs debit spread)
- No weekend exposure (close by Thursday EOD)
- Use straddle premium, not BS-model IV, as the vol gauge
- VIX > 20 → capital preservation mindset (reduce sizing)
