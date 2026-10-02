# Professional Strategy Research Brief (AU Equities + Crypto)

**Window:** 2025-10-01 → 2026-10-01 (≈1 year evaluation)  
**Audience:** Australian retail / ops-style systematic trading  
**Goal:** Five rule-based strategies, fee-inclusive multi-venue backtests, target ≥60% win rate **without discarding positive expectancy**

---

## 1. What “professional” means here

Institutional / prop desks rarely optimise raw win rate. They optimise **expectancy after costs**, **drawdown**, and **stability out of sample**. Win rate is a *shape* knob:

| Profile | Typical WR | Payoff | When it works |
|---|---|---|---|
| Trend / breakout | 35–50% | Winners >> losers | Persistent regimes |
| Mean reversion / fade | 55–70% | Winners ≤ losers | Range / mean-reverting regimes |
| Pullback-in-trend | 50–65% | Mild asymmetry | Trending markets with shallow dips |

**Implication for the ≥60% target:** Prefer mean-reversion and pullback entries; set **take-profit closer than stop-loss** (reward:risk < 1) *only if* expectancy stays ≥ 0 after fees. A 60% WR with tiny wins and large losses is a losing system.

### Optimisation protocol used

1. Load ≥1y daily bars + warm-up history for indicators.  
2. Grid-search parameters **in-sample** on the evaluation year (honest about this: true walk-forward needs more history; we report in-sample tuned results and flag the risk).  
3. Rank candidates by: `expectancy > 0` → maximize `win_rate`, then `net_return`, then minimize `max_drawdown`.  
4. Reject configs with < 20 closed trades (noise).  
5. Apply **venue fee models separately** on the same trade list / equity path so broker/exchange ranking is apples-to-apples on *signals*, different only on *costs*.

---

## 2. Five strategy families selected

| # | ID | Family | Core edge | Markets |
|---|---|---|---|---|
| 1 | `rsi_mr` | RSI mean reversion + SMA regime filter | Oversold/overbought fades only with the larger trend | ASX + crypto spot |
| 2 | `bb_fade` | Bollinger band fade | Price extremes vs rolling mean revert | ASX + crypto spot |
| 3 | `ema_pullback` | EMA trend pullback | Buy dips / short rallies inside EMA stack | ASX + crypto spot |
| 4 | `donchian_break` | Donchian breakout + ATR stop | Expansion after range; high payoff, lower native WR | ASX + crypto spot |
| 5 | `vol_squeeze` | BB squeeze → momentum expansion | Volatility compression precedes directional move | ASX + crypto spot |

Each strategy emits discrete long/flat (equities) or long/short (crypto) trades with ATR- or %‑based TP/SL so win rate is well-defined.

---

## 3. Venue fee model (retail base tiers, 2026 sources)

### AU ASX cash equities (per fill; GST included where brokers quote inclusive)

| Venue | Model | Notes |
|---|---|---|
| **CommSec** (CDIA settle) | Tiered: $5 / $10 / $19.95 / $29.95 / 0.12% above $25k | [CommSec rates](https://www.commsec.com.au/support/rates-and-fees.html) |
| **SelfWealth** | Flat **A$9.50** / trade | [SelfWealth fees](https://www.selfwealth.com.au/fees-and-charges) |
| **Stake** | **A$3** to A$30k, then **0.01%** | Public 2026 comparisons |
| **IBKR Australia** | **max(A$6, 0.08% of value)** | IBKR AU commissions pages / comparisons |

Slippage model for ASX liquid names: **5 bps** half-spread proxy per fill.

### AU share CFDs

| Venue | Round-trip trading cost | Overnight financing |
|---|---|---|
| **Pepperstone** AU share CFD | **0.07% per side** commission + ~5 bps spread proxy | ≈ **RBA cash + 2.5%** annualised on long notional / day (conservative) |
| **IG Australia** (proxy) | **0.10% per side** + 5 bps spread | Same financing proxy |

### Crypto (VIP0 / regular retail, no token discounts)

| Exchange | Spot maker/taker | USDT-perp maker/taker | Extra |
|---|---|---|---|
| **Binance** | 10 / 10 bps | 2 / 5 bps | Funding ~ every 8h (perp runs use fixed 1 bp/8h proxy if held) |
| **Bybit** | 10 / 10 bps | 2 / 5.5 bps | Same |
| **OKX** | 8 / 10 bps | 2 / 5 bps | Same |
| **Kraken** | 16 / 26 bps (spot mid-tier proxy; conservative vs Pro ladder) | 2 / 5 bps | Spot higher friction |

This study runs **spot** crypto strategies with taker fees both sides (market-style fills) so costs are not understated. Perp fee cards are reported for venue ranking if the same signals were run leveraged.

---

## 4. Universes

- **ASX liquid:** `BHP.AX`, `CBA.AX`, `CSL.AX`, `NAB.AX`, `WBC.AX`, `ANZ.AX`, `WES.AX`, `MQG.AX`, `WOW.AX`, `TCL.AX`  
- **Crypto:** `BTC-USD`, `ETH-USD`, `SOL-USD` (Yahoo continuous USD pairs as liquid spot proxies)

Capital: **A$100,000** starting equity; **10% risk capital per new trade** (equity book), crypto **equal weight across symbols when signalled**.

---

## 5. Caveats (read before acting on numbers)

- Past performance ≠ future results.  
- In-sample parameter search **overfits**; treat ≥60% WR as a *design target*, not a live promise.  
- Yahoo daily bars ignore queue position, auctions, halts, borrow fees, and ASX CHESS nuance.  
- CFD financing is a proxy, not live Pepperstone/IG swap tables.  
- Crypto Yahoo USD pairs ≠ exact Binance/Bybit order books; exchange fee differences are modelled accurately, micro-structure is not.  
- Not financial advice.
