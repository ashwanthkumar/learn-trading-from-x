# Sarang Sood (@SarangSood) — Trading Style Notes

*Sources: tweets 2015–2026. Sarcastic tweets excluded. Only genuine trading content.*

---

## Evolution of His Trading

His style has changed significantly over time. Understanding the arc matters.

### Phase 1: Positional Option Seller (pre-2015)
Started as a positional option seller. Edge was **adjustments + price action**. Also sold gut spreads for STT benefit. Was a delta-neutral player from the start.

> *"Before that my only edge in option selling was adjustments & my forever edge of following PA."* — Jan 2021

### Phase 2: Aug 24, 2015 — The Turning Point
China Black Monday. Nifty gap-downed 250 points, then another 250. Wiped out previous months of returns.

> *"Since I'm quick to take my losses, was saved from ruin."* — Jan 2021

This event made him realise that **theta decay + adjustments is not a real edge**. He went deeper into understanding volatility behaviour, how it manifests, and discrepancies in the option chain.

> *"I soon realised that theta decay with sound adjustments is not an edge, which I earlier thought was & which gave me good returns over the years."* — Jan 9, 2021

### Phase 3: Ratio Spreads as Go-To Strategy (2016–2020)
After understanding volatility better, Ratio Spreads became his primary tool when vol was rising.

> *"Whenever vol is on the rise, my go to strategy is always RS. Apart from Jan, Feb & Jul this year when I traded in straddle, 2020 has all been about RS. It's the flexibility of the strategy to trade in both direction & non-direction which I like."* — Nov 29, 2020

- Still using short vega strategies as late as Dec 2020
- Entry signal: vol crush in one side (e.g. put vol crush → enter call ratio or straddle)
- With introduction of weekly options, shifted from positional to more intraday

> *"I also use to be a positional option seller. With the introduction of weeklies, I have become more intraday. I like trading where the max action is taking place."* — Dec 28, 2020

### Phase 4: Expiry-Focused Intraday Trading (2021–2023)
Became heavily focused on expiry-day trading — reading price action on big expiry days (monthly, BankNifty weekly). ATM straddle price was his key gauge.

> *"Mastering price action on big expiry days is a worthy endeavour."* — Dec 2023

> *"Nifty ATM straddle this week making a high of 170 after making a low of 115 today in this downmove. Good vol spike after a long time."* — Dec 20, 2023

Also trading positional: Feb 2023 confirmed holding a **next-month naked strangle** (not 0DTE).

### Phase 5: Long Gamma / Long Vega, Algo-Assisted (2024–2026)
Complete shift to being an option **buyer**.

> *"Have been running a long vega scalping strategy via algo over the past few months, steadily increasing position size with necessary adjustments. Performance has exceeded expectations, though current market volatility has been a tailwind."* — Sep 22, 2024

> *"I'm mostly long gamma specially in this environment, so fast moves is what i wait for."* — Mar 11, 2026

> *"I don't trade expiries much. I'm trading only nifty positional."* — Mar 11, 2026

---

## Current Strategy (2024–2026)

### Instruments
- **Nifty options only** — explicitly does not trade Sensex, FinNifty, or MidCap
- One expiry to track — weekly Nifty

### Core Position: Long Gamma / Long Vega (Positional, Multi-Day)
Holds Nifty option positions across multiple days. Profits from large, fast moves. Waits for volatility expansion.

### Adapts Structure Based on Premium Level
- **Normal / low IV**: Standard long options (direct long gamma/vega exposure)
- **High IV / elevated premiums**: Switches to **debit spreads** — stays long gamma but cuts the theta bleed from expensive premiums

> *"During high premiums I trade in debit spreads more. So the gamma on that move was actually good for me."* — Mar 17, 2026

### Delta Hedging the Long Vol Strategy
Delta hedging is a core part of running the long vol book. It converts long vega positions into actively managed gamma scalps.

> *"Simply delta hedging a long vol strategy can generate substantial benefits in a market like this. It highlights how most market participants are positioned on the other side."* — Jan 14, 2026

### Algo-Assisted Execution
Uses automated execution for the scalping component. Does not code himself — works with tech experts.

> *"I don't have much tech knowledge, so have to work with experts of this field."* — Sep 2024

### Gamma Capture on Expiry Days (Selective)
On active expiry days with high premium, he does engage intraday gamma trades — shifting strikes to stay near ATM.

> *"Good premiums, lots of shifting and capturing gamma. It's the dead expiries which are boring."* — Feb 26, 2026

> *"The strikes are shifting as the index is moving. Aim is to stay at ATMs all the time."* — Dec 30, 2020 (still applies)

---

## Technical Framework

### How He Measures Implied Volatility
Uses ATM straddle price as primary IV gauge. Has a proprietary model.

> *"IVs as a term I use to define premiums/volatility in a broader sense. I have my own prop model to objectively do it. You can do it by checking the ATM straddle price or IVs which are calculated in greeks."* — Dec 28, 2020

> *"Greek IVs are trash for ITM options."* — Dec 30, 2020

Always use the **synthetic future** (not spot) to identify the true ATM strike. Spot and synthetic future differ due to cost of carry.

### India VIX — How He Uses It
VIX is a **range** indicator, not a directional signal.

> *"High VIX does not predict direction. It prices volatility & range expansion."* — Mar 2, 2026

> *"India VIX right now has max weightage for Jan monthly premiums of Nifty."* — Dec 27, 2023

He uses it to understand how expensive options are relative to history and what kind of moves the market is pricing. He does **not** use VIX as a simple signal.

> *"Pls don't follow India Vix to make such decisions"* — Feb 9, 2026

**VIX calibration — COVID vs 2026:**
> *"During COVID, India VIX was around 50 on this same date. If you cannot visualize what 50 VIX looks like: 13 Mar '26: India VIX: 22, Nifty: 23200, Straddle: 500. 13 Mar '20: India VIX: 50, Nifty: 10000, ATM Straddle: 680. That is how expensive uncertainty can get."* — Mar 13, 2026

**VIX > 20 = capital preservation mode:**
> *"India VIX now above 20. During such times 'return of capital' becomes more important than the 'return on capital'."* — Mar 4, 2026

### How He Reads Volatility Behaviour
- Volatility spikes and then normalises — but the **duration** of elevated vol is what breaks strategies, not the intensity

> *"They are not fragile because volatility rises. They are fragile because volatility sometimes stays elevated much longer than traders expect. It is often not the intensity of volatility that causes problems, but its duration."* — Mar 11, 2026

- Markets **overprice catastrophe** first, then slowly reprice toward probability

> *"It first prices catastrophe & then slowly prices probability."* — Mar 11, 2026

- Pre-event low premiums are an opportunity — calm before big events rarely lasts

> *"When premiums are low before a big event, the calm rarely lasts. Some news appears out of nowhere & the market rapidly expands volatility ahead of that event."* — Jan 7, 2026

**The "false calm" trap (Aug 5, 2024 example):**
On Aug 2, 2024 (Friday), Nifty dropped 200pts, India VIX closed at 14, ATM straddle at 315. The following Monday (Aug 5) saw a 400+ pt gap-down. The low VIX and straddle price gave a false sense of calm. This is the exact setup to watch for: **market prices low vol while conditions for a large move are already in place**.

> *"5th Aug '24 (Monday) is a highly underrated day of market volatility in recent times, one that isn't discussed often enough."* — Jan 11, 2025

**Theta delay as a signal:**
When theta decay fails to show up on schedule, the delay itself becomes a trading signal — the market is storing energy.

> *"Theta d̶e̶c̶a̶y̶ delay is an edge"* — Feb 19, 2026 (crossed out "decay", replaced with "delay")

**Straddle vs OTM asymmetry (the false decay trap):**
Even when the ATM straddle appears to decay normally, directional OTM options can explode multifold — catching sellers off guard.

> *"Straddle down 15% / OTM put option up 50% / Free money??"* — Feb 9, 2026

> *"Nifty up 100pts from day low / OTM puts up 40%"* — Feb 16, 2026

### OTM Option Analysis
Cannot look at a single OTM option in isolation. Must compare to index movement or greeks. OTM strangle analysis is unreliable because a delta move creates a skew.

> *"We can't look at a single OTM option. It has to be seen in comparison to index or greeks. We can't look at OTM strangle because delta move can create a skew."* — Dec 28, 2020

### Delta Management (Straddle / Long Gamma)
When running a straddle or long gamma position, he targets ~delta 50 for each leg and shifts strikes as the index moves — always trying to stay near ATM.

> *"The delta needs to be around 50 for both the options. So the strikes keep adjusting around that figure."* — Dec 30, 2020

### Long Vega vs Gamma Scalping
He draws a clear distinction:

> *"Gamma scalping is different. Because long vega is against time. So need to book. In all long vega strategies, adjustments are just a way to book profits. Opposite for short vega strategies which we call as adjustment cost."* — Dec 29, 2020

- Long vega: adjustments = **profit booking mechanism**
- Short vega: adjustments = **cost/damage control**

### Expiry-Day Mechanics
**Settlement calculation:** Expiry is the average of the last 30 minutes of the spot price — not the closing print.

> *"Expiry is calculated as the average of the last 30 minutes of the spot price."* — Feb 12, 2026

**3pm gamma:** Post-3pm on expiry days is consistently the most dangerous time for option sellers. He watches this window carefully.

> *"Post 3pm gamma is the toughest for option sellers"* — Nov 27, 2025

> *"This 3pm gamma was the icing on the top to end the October series"* — Oct 28, 2025

**Narrative risk on expiry days:** Large players can plant news events near expiry to cause massive directional moves.

> *"Last week during Sensex expiry, a carefully planted fake news story caused a huge upside tick where call options went more than 100x. When uncertainty is high, markets become extremely sensitive to narratives. And the person who controls the narrative controls the volatility."* — Mar 9, 2026

### Market Microstructure
Watches OTM option flows across multiple days to identify retail capitulation as entry signals.

> *"Same pattern again in OTM options on both sides over the last 3 days. Retail panics & exits. Smart money uses that panic as an entry window."* — Feb 6, 2026

Institutional money is active in intraday options — this is not purely retail flow.

> *"1000s of crores of bank money is being used in intraday option trading fyi"* — Feb 14, 2026

---

## Risk Management

- **Position sizing and discipline** over intelligence in high-vol environments

> *"High volatility markets don't reward intelligence. They reward discipline & position sizing."* — Mar 9, 2026

- Quick to take losses — this has been a constant from the very beginning (saved him in 2015)

> *"Since I'm quick to take my losses, was saved from ruin."* — Jan 2021

- No gamma/theta exposure over weekends — manages or closes positions before weekend

> *"Gamma theta only on trading days."* — Dec 13, 2025

- Scales up gradually with proven performance

> *"Steadily increasing position size with necessary adjustments."* — Sep 2024

- Trades actively even in high-vol regimes, but with caution — tries to stay on the right side

> *"I'm trading actively but with extreme caution. Trying to stay in the right side of the volatility."* — Mar 12, 2026

- On big high-conviction expiry days: willing to go all in

> *"Yeah had to go all in myself."* — Dec 28, 2023

- When VIX is above 20: shift focus to **capital preservation**, not returns

> *"Return of capital becomes more important than the return on capital."* — Mar 4, 2026

---

## Core Beliefs About Edge

These reflect what he genuinely thinks about finding and sustaining an edge:

> *"I soon realised that theta decay with sound adjustments is not an edge."* — Jan 2021

> *"Markets change so quickly that even if some strategy was doing well 2 years ago, most likely it will stop acting soon. If a trader is making consistent money in the same strategy year after year, his edge lies somewhere else not in the strategy itself."* — Jan 9, 2021

> *"You need to know when to use which strategy & use adjustments to fully extract its potential or if view goes wrong then minimize damage or even come out profitable."* — Jan 9, 2021

> *"Putting all efforts in backtesting a strategy where maximum crowd is (like a straddle) & finding perfect entry/exits with a click of a button will not give an edge."* — Jan 9, 2021

> *"Challenge is always to adapt according to changing regime."* — Sep 2024

> *"No market regime is ever truly easy or impossibly hard to trade. If it feels easy, it only means you discovered an edge most participants still fail to exploit consistently. When it feels hard, it usually means your old edge stopped working while the market quietly evolved."* — Feb 25, 2026

His actual edge, as he describes it: **reading volatility behaviour, understanding where it manifests, identifying discrepancies in the option chain, and adapting the strategy to the current regime.** Price action is a constant input throughout.
